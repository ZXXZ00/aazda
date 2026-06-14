import os
import time
import schedule
from queue import Queue

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

import sys
import signal

from ingest import ingest_paths
from opensearch import delete_by_path_query
from path_env import HOME_DIRECTORY, IGNORE_DIR, TRASH_DIR
from util import is_hidden, walk


class FileEventHandler(FileSystemEventHandler):
    queue: Queue[FileSystemEvent]
    paths_to_ignore: tuple[str, ...]
    trash_dir: str | None

    def __init__(self, paths_to_ignore: tuple[str, ...], trash_dir: str | None = None):
        self.queue = Queue()
        self.paths_to_ignore = paths_to_ignore
        self.trash_dir = trash_dir

    def process(self) -> None:
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

        while not self.queue.empty():
            event = self.queue.get()
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
            children = walk(dest, self.paths_to_ignore)
            to_upsert.update(children)
            # since the children is full path, need to get src + relative path
            to_delete.update(map(lambda child: src + child[len(dest) :], children))
        print("to_upsert", to_upsert)
        print("to_delete", to_delete)

        # after all the processing
        # the to_upsert and to_delete still doesn't necessarily is 100% correct
        # because a file can get created and deleted
        # or created and moved else where
        # it would require much more complex logic to handle that
        # as long we can capture all the creation, upate, delete, move
        # extra false positive is fine

        # TODO: error handling
        ingest_paths(to_upsert, True)
        delete_by_path_query(list(to_delete))

    def on_any_event(self, event):
        if event.is_synthetic:
            return
        if event.is_directory and event.event_type == "modified":
            return
        if event.src_path.startswith(
            self.paths_to_ignore
        ) or event.dest_path.startswith(self.paths_to_ignore):
            return
        if is_hidden(event.src_path):
            return
        self.queue.put(event)


observer = Observer()
event_handler = FileEventHandler(paths_to_ignore=IGNORE_DIR, trash_dir=TRASH_DIR)
schedule.every(60).seconds.do(event_handler.process)
observer.schedule(event_handler, HOME_DIRECTORY, recursive=True)
observer.start()


def signal_handler(sig, frame):
    observer.stop()
    observer.join()
    schedule.clear()
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)


try:
    while True:
        schedule.run_pending()
        time.sleep(1)
finally:
    observer.stop()
    observer.join()
    schedule.clear()
