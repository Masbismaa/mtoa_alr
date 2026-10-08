// ikon SVG garis gaya Tabler Icons. Path-nya disalin dari app/templates/components/icon.html
// (cuma yg dipake komponen React). Nambah ikon: salin path dari icon.html ke sini.
const ICON_PATH_DICT = {
  arrow_down: "M12 5v14 M19 12l-7 7-7-7",
  arrow_up: "M12 19V5 M5 12l7-7 7 7",
  chevron_left: "M15 18l-6-6 6-6",
  chevron_right: "M9 18l6-6-6-6",
  columns: "M4 4h6v16H4z M14 4h6v16h-6z",
  copy: "M9 9h13v13H9z M5 15H2V2h13v3",
  download: "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4 M7 10l5 5 5-5 M12 15V3",
  eye: "M1 12s4-8 11-8 11 8 11 8-4 8-11 8S1 12 1 12z M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
  link: "M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7 M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7",
  paperclip: "M21.4 11.1l-9.2 9.2a6 6 0 0 1-8.5-8.5l9.2-9.2a4 4 0 0 1 5.7 5.7l-9.2 9.2a2 2 0 0 1-2.8-2.8l8.5-8.5",
  plus: "M12 5v14 M5 12h14",
  refresh: "M20 11a8.1 8.1 0 0 0-15.5-2 M4 5v4h4 M4 13a8.1 8.1 0 0 0 15.5 2 M20 19v-4h-4",
  search: "M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16z M21 21l-4.35-4.35",
  selector: "M8 9l4-4 4 4 M16 15l-4 4-4-4",
  alert_triangle: "M12 9v4 M12 17h.01 M10.3 3.9L1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z",
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
