import os
import time
import schedule
from queue import Queue, Empty

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

import sys
import signal
import threading

import parsers
import local_db
from datetime import datetime
from path_env import HOME_DIRECTORY, IGNORE_DIR, TRASH_DIR
from util import is_hidden, walk

_sync_in_progress = True


def is_file_stable(path: str, min_age_seconds: float = 2.0) -> bool:
    """Check that the file hasn't been modified very recently (likely still being written)."""
    try:
        mtime = os.path.getmtime(path)
        return (time.time() - mtime) >= min_age_seconds
    except OSError:
        return False


class FileEventHandler(FileSystemEventHandler):
    queue: Queue[FileSystemEvent]
    paths_to_ignore: tuple[str, ...]
    trash_dir: str | None

    def __init__(self, paths_to_ignore: tuple[str, ...], trash_dir: str | None = None):
        self.queue = Queue()
        self.paths_to_ignore = paths_to_ignore
        self.trash_dir = trash_dir
        self._deferred: set[str] = set()
        self._processing_lock = threading.Lock()

    def process(self) -> None:
        global _sync_in_progress
        if _sync_in_progress:
            return
        files_upsert: set[str] = set()
        files_moved_from: dict[str, str] = {}
        files_moved_to: dict[str, str] = {}
        files_deleted: set[str] = set()
        dir_upsert: set[str] = set()
        dir_moved_from: dict[str, str] = {}
        dir_moved_to: dict[str, str] = {}
        dir_deleted: set[str] = set()

        def process_event(
            event: FileSystemEvent,
            upsert: set[str],
            moved_from: dict[str, str],
            moved_to: dict[str, str],
            deleted: set[str],
        ):
            try:
                src_path = os.fsdecode(event.src_path)
            except Exception as err:
                print("ERROR: while decoding src_path", err)
                return
            match event.event_type:
                case "created" | "modified":
                    deleted.discard(src_path)
                    upsert.add(src_path)
                    result = moved_to.get(src_path)
                    if result:
                        # if the file was moved to, the src should be deleted
                        del moved_to[src_path]
                        del moved_from[result]
                        deleted.add(result)
                case "moved":
                    try:
                        dest_path = os.fsdecode(event.dest_path)
                    except Exception as err:
                        print("ERROR: while decoding dest_path", err)
                        return

                    # in case of moving to trash or moving from trash
                    if self.trash_dir and dest_path.startswith(self.trash_dir):
                        upsert.discard(src_path)
                        deleted.add(src_path)
                        return
                    if self.trash_dir and src_path.startswith(self.trash_dir):
                        deleted.discard(dest_path)
                        upsert.add(dest_path)
                        return

                    moved_from[src_path] = dest_path
                    moved_to[dest_path] = src_path
                    if src_path in upsert:
                        upsert.remove(src_path)
                        upsert.add(dest_path)

                case "deleted":
                    upsert.discard(src_path)
                    deleted.add(src_path)
                    result = moved_to.get(src_path)
                    if result:
                        # if the file was moved to, the src should be deleted
                        del moved_to[src_path]
                        del moved_from[result]
                        deleted.add(result)
                case _:
                    print("ERROR: unknown file event type")

        while True:
            try:
                event = self.queue.get_nowait()
            except Empty:
                break
            if event.is_directory:
                process_event(
                    event, dir_upsert, dir_moved_from, dir_moved_to, dir_deleted
                )
            else:
                process_event(
                    event, files_upsert, files_moved_from, files_moved_to, files_deleted
                )
            self.queue.task_done()

        print("file_upsert", files_upsert)
        print("file_moved_from", files_moved_from)
        print("file_moved_to", files_moved_to)
        print("file_deleted", files_deleted)
        print("dir_upsert", dir_upsert)
        print("dir_moved_from", dir_moved_from)
        print("dir_moved_to", dir_moved_to)
        print("dir_deleted", dir_deleted)

        # when a dir is moved or deleted, the files inside should be checked too
        to_upsert = files_upsert | dir_upsert
        to_delete = files_deleted | dir_deleted
        for src, dest in dir_moved_from.items():
            to_delete.add(src)
            to_upsert.add(dest)
            children_list = walk(dest, self.paths_to_ignore)
            children = []
            for child in children_list:
                child_abs = os.path.abspath(child)
                if not os.path.isdir(child_abs):
                    _, ext = os.path.splitext(child_abs)
                    if ext and parsers.is_junk_ext(ext.lower()):
                        continue
                children.append(child_abs)
            to_upsert.update(children)
            # since the children is full path, need to get src + relative path
            to_delete.update(map(lambda child: src + child[len(dest) :], children))

        # handle single file moves and renames
        for src, dest in files_moved_from.items():
            to_delete.add(src)
            to_upsert.add(dest)

        # Merge in previously deferred unstable paths for retry
        if self._deferred:
            to_upsert.update(self._deferred)
            self._deferred.clear()

        print("to_upsert", to_upsert)
        print("to_delete", to_delete)

        # after all the processing
        # the to_upsert and to_delete still doesn't necessarily is 100% correct
        # because a file can get created and deleted
        # or created and moved else where
        # it would require much more complex logic to handle that
        # as long we can capture all the creation, upate, delete, move
        # extra false positive is fine

        # Process deletions
        for p in to_delete:
            try:
                local_db.delete_path(p)
            except Exception as e:
                print(f"ERROR: failed to delete {p} from Qdrant: {e}", file=sys.stderr)

        # Process upserts (with file stability check to avoid indexing mid-write)
        for p in to_upsert:
            try:
                if not os.path.exists(p):
                    continue
                # Defer files still being written to (modified < 2s ago)
                if not os.path.isdir(p) and not is_file_stable(p):
                    self._deferred.add(p)
                    continue
                doc = parsers.parse_file(p)
                if doc is None:
                    continue  # Junk file, skip
                local_db.upsert_document(doc)
            except Exception as e:
                print(f"ERROR: failed to index {p} in Qdrant: {e}", file=sys.stderr)

    def on_any_event(self, event):
        if event.is_synthetic:
            return
        if event.is_directory and event.event_type == "modified":
            return
        dest_path = getattr(event, "dest_path", None)
        if event.src_path.startswith(self.paths_to_ignore) or (
            dest_path and dest_path.startswith(self.paths_to_ignore)
        ):
            return
        if is_hidden(event.src_path):
            return
            
        # Ignore files with junk extensions
        if not event.is_directory:
            _, ext = os.path.splitext(event.src_path)
            if ext and parsers.is_junk_ext(ext.lower()):
                return
            if dest_path:
                _, dest_ext = os.path.splitext(dest_path)
                if dest_ext and parsers.is_junk_ext(dest_ext.lower()):
                    return
                    
        self.queue.put(event)


def sync_directory(watch_dir: str, stop_event: threading.Event | None = None):
    global _sync_in_progress
    _sync_in_progress = True
    print(f"Sync: Starting startup synchronization for directory: {watch_dir}")
    try:
        from util import walk
        from path_env import DB_DIR
        # Ignore the database directory specifically to prevent feedback loops
        extended_ignore = IGNORE_DIR + (DB_DIR,)
        disk_paths_list = walk(watch_dir, extended_ignore)
        disk_paths = set()
        for p in disk_paths_list:
            p_abs = os.path.abspath(p)
            if not os.path.isdir(p_abs):
                _, ext = os.path.splitext(p_abs)
                if ext and parsers.is_junk_ext(ext.lower()):
                    continue
            disk_paths.add(p_abs)
        print(f"Sync: Found {len(disk_paths)} valid files/folders on disk.")

        # Track database path info: path -> { updated_at, actual_chunks_found, expected_total_chunks }
        db_paths = {}
        try:
            offset = None
            while True:
                records, offset = local_db.client.scroll(
                    collection_name=local_db.COLLECTION_NAME,
                    limit=5000,
                    with_payload=["path", "updated_at", "total_chunks"],
                    with_vectors=False,
                    offset=offset
                )
                for r in records:
                    p = r.payload.get("path")
                    updated_at = r.payload.get("updated_at")
                    expected_total = r.payload.get("total_chunks", 1)  # Default to 1 if not set yet
                    if p:
                        p_abs = os.path.abspath(p)
                        if p_abs not in db_paths:
                            db_paths[p_abs] = {
                                "updated_at": updated_at,
                                "actual_chunks": 1,
                                "expected_total": expected_total
                            }
                        else:
                            db_paths[p_abs]["actual_chunks"] += 1
                            if updated_at > db_paths[p_abs]["updated_at"]:
                                db_paths[p_abs]["updated_at"] = updated_at
                            if expected_total > db_paths[p_abs]["expected_total"]:
                                db_paths[p_abs]["expected_total"] = expected_total
                if offset is None:
                    break
        except Exception as e:
            print(f"Sync Error scrolling db paths: {e}", file=sys.stderr)

        stale_candidates = set(db_paths.keys()) - disk_paths
        # Only delete entries for files confirmed gone from disk.
        # Files merely absent from walk() (e.g., due to macOS permission
        # restrictions on ~/Desktop, ~/Documents, ~/Downloads) should be kept.
        to_delete = {p for p in stale_candidates if not os.path.exists(p)}
        skipped = len(stale_candidates) - len(to_delete)
        if skipped:
            print(f"Sync: Keeping {skipped} DB entries for files not reachable by walk (likely permissions).")
        if to_delete:
            print(f"Sync: Deleting {len(to_delete)} truly deleted files/folders from Qdrant...")
            for p in to_delete:
                try:
                    local_db.delete_path(p)
                except Exception as e:
                    print(f"Sync Error deleting {p}: {e}", file=sys.stderr)

        to_ingest = []
        for p in disk_paths:
            if not os.path.exists(p):
                continue
            stats = os.stat(p)
            mtime = datetime.fromtimestamp(stats.st_mtime).isoformat()
            
            is_incomplete = False
            if p in db_paths:
                info = db_paths[p]
                is_incomplete = info["actual_chunks"] < info["expected_total"]
                
            is_dir = os.path.isdir(p)
            # Re-index if:
            # 1. Path is not in the database.
            # 2. Disk file is newer than database record (files only).
            # 3. Database is missing chunks (indexing was interrupted/aborted).
            if p not in db_paths or (not is_dir and mtime > db_paths[p]["updated_at"]) or is_incomplete:
                to_ingest.append(p)

        if to_ingest:
            print(f"Sync: Indexing {len(to_ingest)} new or modified files/folders...")
            for idx, p in enumerate(to_ingest):
                if stop_event and stop_event.is_set():
                    print("Sync: Interrupted by shutdown signal.")
                    break
                try:
                    doc = parsers.parse_file(p)
                    if doc is None:
                        continue  # Junk file, skip
                    local_db.upsert_document(doc)
                    if (idx + 1) % 50 == 0:
                        print(f"  Indexed {idx + 1}/{len(to_ingest)} items...")
                except Exception as e:
                    print(f"Sync Error indexing {p}: {e}", file=sys.stderr)
                time.sleep(0.002)

        print("Sync: Startup synchronization completed successfully!")
    except Exception as e:
        print(f"Sync Error during sync_directory: {e}", file=sys.stderr)
    finally:
        _sync_in_progress = False

_observer = None
_scheduler_thread = None
_stop_event = None

def start_watcher(watch_dir: str, interval: int):
    global _observer, _scheduler_thread, _stop_event
    if _observer is not None:
        print("Watcher already running.")
        return _observer

    print(f"Starting watcher on directory: {watch_dir}")
    print(f"Schedule processing interval: {interval} seconds")

    _observer = Observer()
    from path_env import DB_DIR
    extended_ignore = IGNORE_DIR + (DB_DIR,)
    event_handler = FileEventHandler(paths_to_ignore=extended_ignore, trash_dir=TRASH_DIR)
    
    import schedule as sched_lib
    
    local_scheduler = sched_lib.Scheduler()
    local_scheduler.every(interval).seconds.do(event_handler.process)
    
    _stop_event = threading.Event()
    
    def run_scheduler():
        while not _stop_event.is_set():
            local_scheduler.run_pending()
            time.sleep(1)
            
    _observer.schedule(event_handler, watch_dir, recursive=True)
    _observer.start()
    
    _scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    _scheduler_thread.start()
    
    # Run startup synchronization in a background daemon thread
    sync_thread = threading.Thread(target=sync_directory, args=(watch_dir, _stop_event), daemon=True)
    sync_thread.start()
    
    return _observer

def stop_watcher():
    global _observer, _scheduler_thread, _stop_event
    if _stop_event:
        _stop_event.set()
    if _observer:
        print("Stopping watcher observer...")
        _observer.stop()
        _observer.join()
        _observer = None
    if _scheduler_thread:
        _scheduler_thread.join(timeout=3)
        _scheduler_thread = None
    _stop_event = None
    print("Watcher stopped.")


if __name__ == "__main__":
    watch_dir_arg = sys.argv[1] if len(sys.argv) > 1 else HOME_DIRECTORY
    interval_arg = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    
    start_watcher(watch_dir_arg, interval_arg)
    
    def signal_handler(sig, frame):
        stop_watcher()
        sys.exit(0)
        
    signal.signal(signal.SIGINT, signal_handler)
    
    print("Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop_watcher()

