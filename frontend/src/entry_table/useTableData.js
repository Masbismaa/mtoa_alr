// state data tabel: isi dari server (payload) + ngambil ulang lewat API tiap urutan/filter/halaman berubah.
//
// Aturan penting (biar ga ada bug "data ketuker"):
// - server = sumber kebenaran. Abis request, seluruh payload diganti sama balasan server
//   (termasuk kriteria yg udah dirapihin server), bukan ditambal di browser.
// - cuma request TERAKHIR yg dipake. Request lama dibatalin (AbortController), jadi klik cepet berkali-kali
//   ga bikin tabel nampilin hasil klik sebelumnya.
// - URL browser ikut diganti (history.pushState) biar refresh, bookmark, & tombol Back/Forward tetep bener.
import { useCallback, useEffect, useRef, useState } from "react";
import { getJson } from "../shared/api.js";
import { buildUrl, parseQueryText } from "../shared/queryString.js";
import { showStatus } from "../shared/statusBar.js";

// event buat panel Kriteria Pencarian (js/components/selection_panel.js) biar isiannya ikut berubah
export const QUERY_CHANGED_EVENT = "alr:table-query-changed";

function notifyQueryChanged(query) {
  document.dispatchEvent(new CustomEvent(QUERY_CHANGED_EVENT, { detail: { query } }));
}

// cara nyatet perubahan ke riwayat browser
export const HISTORY_PUSH = "push"; // klik user: bisa di-Back
export const HISTORY_NONE = "none"; // lagi nanggepin tombol Back/Forward: riwayat jangan diubah

export default function useTableData(initialPayload) {
  const [payload, setPayload] = useState(initialPayload);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const controllerRef = useRef(null);
  // alamat API & halaman ga pernah berubah selama halaman kebuka
  const apiUrl = initialPayload.api_url;
  const pageUrl = initialPayload.page_url;

  const load = useCallback(async (query, page, historyMode = HISTORY_PUSH) => {
    if (controllerRef.current) controllerRef.current.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    setIsLoading(true);
    try {
      const data = await getJson(buildUrl(apiUrl, query, page), controller.signal);
      setPayload(data);
      setError(null);
      if (historyMode === HISTORY_PUSH) {
        window.history.pushState({ alrEntryTable: true }, "", buildUrl(data.page_url, data.query, data.page, data.anchor));
      }
      notifyQueryChanged(data.query);
      return data;
    } catch (loadError) {
      if (loadError.name === "AbortError") return null;
      setError(loadError);
      showStatus(loadError.message, "danger");
      return null;
    } finally {
      // request yg udah kalah sama request baru ga boleh matiin indikator loading punya request baru
      if (controllerRef.current === controller) {
        controllerRef.current = null;
        setIsLoading(false);
      }
    }
  }, [apiUrl]);

  // tombol Back/Forward browser: ambil lagi data sesuai URL (riwayatnya ga ditambah)
  useEffect(() => {
    function handlePopState() {
      if (window.location.pathname !== pageUrl) return;
      const { query, page } = parseQueryText(window.location.search);
      load(query, page, HISTORY_NONE);
    }
    window.addEventListener("popstate", handlePopState);
    return () => {
      window.removeEventListener("popstate", handlePopState);
      if (controllerRef.current) controllerRef.current.abort();
    };
  }, [load, pageUrl]);

  return { payload, isLoading, error, load };
}
