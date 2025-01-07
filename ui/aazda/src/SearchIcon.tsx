export const SearchIcon = ({ color = '#888888', width = 24, height = 24 }) => (
  <svg
    width={width}
    height={height}
    viewBox="0 0 24 24"
    xmlns="http://www.w3.org/2000/svg"
    fill="none"
    stroke={color}
    strokeWidth="1.5"
    strokeLinecap="round"
    strokeLinejoin="round"
    className="icons"
  >
    <circle cx="11" cy="11" r="8" stroke-width="2" fill="none"/>
    <line x1="16.5" y1="16.5" x2="23" y2="23" stroke-width="2"/>
  </svg>
);