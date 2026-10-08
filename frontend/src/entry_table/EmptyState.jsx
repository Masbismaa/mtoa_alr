// isi kartu kalau ga ada data. Teks & tombolnya dari server (entry_table_service.py:build_empty_state)
import Icon from "../shared/Icon.jsx";

export default function EmptyState({ empty }) {
  const action = empty.action;
  return (
    <div className="empty">
      <div className="empty-icon"><Icon name={empty.icon} /></div>
      <p className="empty-title">{empty.title}</p>
      <p className="empty-subtitle text-secondary">{empty.subtitle}</p>
      {action && (
        <div className="empty-action">
          <a href={action.url} className={"btn" + (action.is_primary ? " btn-primary" : "")}>
            {action.icon && <Icon name={action.icon} />} {action.label}
          </a>
        </div>
      )}
    </div>
  );
}
