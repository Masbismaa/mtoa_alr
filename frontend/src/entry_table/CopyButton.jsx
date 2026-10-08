// tombol copy kecil di sel tabel (gaya sama kayak components/copy_button.html, is_icon_only)
import { useEffect, useRef, useState } from "react";
import Icon from "../shared/Icon.jsx";
import { copyText } from "../shared/clipboard.js";
import { showStatus } from "../shared/statusBar.js";

const RESET_MS = 1500;

export default function CopyButton({ text, label }) {
  const [isCopied, setIsCopied] = useState(false);
  const timerRef = useRef(null);

  useEffect(() => () => window.clearTimeout(timerRef.current), []);

  async function handleClick() {
    try {
      await copyText(text);
      setIsCopied(true);
      window.clearTimeout(timerRef.current);
      timerRef.current = window.setTimeout(() => setIsCopied(false), RESET_MS);
    } catch (error) {
      showStatus("Gagal menyalin, coba blok teksnya manual", "danger");
    }
  }

  return (
    <button
      type="button"
      className={"btn btn-sm btn-icon copy-button" + (isCopied ? " is-copied" : "")}
      aria-label={label}
      title={label}
      onClick={handleClick}
    >
      <Icon name="copy" />
      <span className="visually-hidden">{isCopied ? "Tersalin ✓" : label}</span>
    </button>
  );
}
