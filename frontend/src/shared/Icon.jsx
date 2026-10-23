// ikon SVG dari Tabler Icons v3.31.0 (MIT). Path-nya disalin dari app/templates/components/icon.html
// (cuma yg dipake komponen React). Nambah ikon: salin path dari icon.html ke sini.
const ICON_PATH_DICT = {
  arrow_down: "M12 5l0 14 M18 13l-6 6 M6 13l6 6",
  arrow_up: "M12 5l0 14 M18 11l-6 -6 M6 11l6 -6",
  chevron_left: "M15 6l-6 6l6 6",
  chevron_right: "M9 6l6 6l-6 6",
  columns: "M4 6l5.5 0 M4 10l5.5 0 M4 14l5.5 0 M4 18l5.5 0 M14.5 6l5.5 0 M14.5 10l5.5 0 M14.5 14l5.5 0 M14.5 18l5.5 0",
  copy: "M7 7m0 2.667a2.667 2.667 0 0 1 2.667 -2.667h8.666a2.667 2.667 0 0 1 2.667 2.667v8.666a2.667 2.667 0 0 1 -2.667 2.667h-8.666a2.667 2.667 0 0 1 -2.667 -2.667z M4.012 16.737a2.005 2.005 0 0 1 -1.012 -1.737v-10c0 -1.1 .9 -2 2 -2h10c.75 0 1.158 .385 1.5 1",
  download: "M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2 -2v-2 M7 11l5 5l5 -5 M12 4l0 12",
  eye: "M10 12a2 2 0 1 0 4 0a2 2 0 0 0 -4 0 M21 12c-2.4 4 -5.4 6 -9 6c-3.6 0 -6.6 -2 -9 -6c2.4 -4 5.4 -6 9 -6c3.6 0 6.6 2 9 6",
  link: "M9 15l6 -6 M11 6l.463 -.536a5 5 0 0 1 7.071 7.072l-.534 .464 M13 18l-.397 .534a5.068 5.068 0 0 1 -7.127 0a4.972 4.972 0 0 1 0 -7.071l.524 -.463",
  paperclip: "M15 7l-6.5 6.5a1.5 1.5 0 0 0 3 3l6.5 -6.5a3 3 0 0 0 -6 -6l-6.5 6.5a4.5 4.5 0 0 0 9 9l6.5 -6.5",
  plus: "M12 5l0 14 M5 12l14 0",
  refresh: "M20 11a8.1 8.1 0 0 0 -15.5 -2m-.5 -4v4h4 M4 13a8.1 8.1 0 0 0 15.5 2m.5 4v-4h-4",
  search: "M10 10m-7 0a7 7 0 1 0 14 0a7 7 0 1 0 -14 0 M21 21l-6 -6",
  selector: "M8 9l4 -4l4 4 M16 15l-4 4l-4 -4",
  trash: "M4 7l16 0 M10 11l0 6 M14 11l0 6 M5 7l1 12a2 2 0 0 0 2 2h8a2 2 0 0 0 2 -2l1 -12 M9 7v-3a1 1 0 0 1 1 -1h4a1 1 0 0 1 1 1v3",
  alert_triangle: "M12 9v4 M10.363 3.591l-8.106 13.534a1.914 1.914 0 0 0 1.636 2.871h16.214a1.914 1.914 0 0 0 1.636 -2.87l-8.106 -13.536a1.914 1.914 0 0 0 -3.274 0z M12 16h.01",
};

export default function Icon({ name, className = "" }) {
  return (
    <svg
      className={"icon" + (className ? " " + className : "")}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d={ICON_PATH_DICT[name] || ""} />
    </svg>
  );
}
