// salin teks ke clipboard. Clipboard API cuma jalan di https/localhost,
// akses lewat http biasa (misal IP kantor) pake cara lama (textarea + execCommand). Sama kayak js/components/copy_button.js
function copyWithFallback(text) {
  const textareaEl = document.createElement("textarea");
  textareaEl.value = text;
  textareaEl.setAttribute("readonly", "");
  textareaEl.className = "visually-hidden";
  document.body.append(textareaEl);
  textareaEl.select();
  const isCopied = document.execCommand("copy");
  textareaEl.remove();
  if (!isCopied) throw new Error("copy gagal");
}

export async function copyText(text) {
  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(text);
      return;
    } catch (error) {
      // izin clipboard ditolak browser -> coba cara lama
    }
  }
  copyWithFallback(text);
}
