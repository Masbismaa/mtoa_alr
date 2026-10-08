// footer kartu tabel: info halaman + navigasi (sama kayak components/pagination.html).
// daftar nomor halaman (page_list, null = "…") dihitung server. Link-nya tetep href beneran,
// jadi Ctrl+klik / klik tengah tetep bisa buka di tab baru; klik biasa diganti ngambil data tanpa reload.
import Icon from "../shared/Icon.jsx";
import { isPlainClick } from "../shared/events.js";

export default function Pagination({ page, pages, pageList, buildPageHref, onPageChange }) {
  if (pages <= 1) return null;

  function renderLink(targetPage, content, ariaLabel) {
    return (
      <a
        className="page-link"
        href={buildPageHref(targetPage)}
        aria-label={ariaLabel}
        onClick={(event) => {
          if (!isPlainClick(event)) return;
          event.preventDefault();
          onPageChange(targetPage);
        }}
      >
        {content}
      </a>
    );
  }

  return (
    <div className="card-footer d-flex flex-wrap align-items-center gap-2">
      <p className="m-0 text-secondary">Halaman <strong>{page}</strong> dari <strong>{pages}</strong></p>
      <nav className="ms-auto" aria-label="Navigasi halaman">
        <ul className="pagination m-0">
          <li className={"page-item" + (page > 1 ? "" : " disabled")}>
            {page > 1
              ? renderLink(page - 1, <Icon name="chevron_left" />, "Halaman sebelumnya")
              : <span className="page-link" aria-hidden="true"><Icon name="chevron_left" /></span>}
          </li>
          {pageList.map((pageNumber, index) => {
            if (pageNumber === null) {
              // "…" ga punya nomor, jadi key-nya pake posisi
              return <li className="page-item disabled" key={"gap-" + index}><span className="page-link">&hellip;</span></li>;
            }
            if (pageNumber === page) {
              return <li className="page-item active" key={pageNumber}><span className="page-link" aria-current="page">{pageNumber}</span></li>;
            }
            return <li className="page-item" key={pageNumber}>{renderLink(pageNumber, pageNumber)}</li>;
          })}
          <li className={"page-item" + (page < pages ? "" : " disabled")}>
            {page < pages
              ? renderLink(page + 1, <Icon name="chevron_right" />, "Halaman berikutnya")
              : <span className="page-link" aria-hidden="true"><Icon name="chevron_right" /></span>}
          </li>
        </ul>
      </nav>
    </div>
  );
}
