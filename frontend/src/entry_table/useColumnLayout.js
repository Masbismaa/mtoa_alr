// layout kolom (kolom yg disembunyiin + lebar) yg disimpen per akun lewat POST /settings/table-layout.
//
// Layout dipegang browser sejak halaman dibuka, BUKAN diambil ulang dari tiap balasan API:
// kalau simpanan masih nunggu (debounce), balasan API bisa bawa layout lama & bikin perubahan user "balik lagi".
import { useCallback, useEffect, useRef, useState } from "react";
import { postJson } from "../shared/api.js";
import { showStatus } from "../shared/statusBar.js";

export const MIN_WIDTH = 60;
export const MAX_WIDTH = 800;
// disimpen setelah user berhenti geser/klik sebentar, biar ga ngirim tiap piksel
const SAVE_DELAY_MS = 600;
export const IDLE_STATUS_TEXT = "Widths & columns are saved to your account automatically.";

export function clampWidth(width) {
  return Math.round(Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, width)));
}

// id acak per tab: server nolak kiriman lama dari tab yg sama yg telat nyampe (sequence lebih kecil)
function createClientId() {
  if (window.crypto && typeof window.crypto.randomUUID === "function") return window.crypto.randomUUID();
  return `tab-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

function normalizeLayout(layout) {
  return {
    hidden_list: Array.isArray(layout && layout.hidden_list) ? layout.hidden_list : [],
    width_dict: layout && layout.width_dict && typeof layout.width_dict === "object" ? layout.width_dict : {},
  };
}

export default function useColumnLayout({ tableKey, layoutUrl, initialLayout, defaultLayout, defaultWidthDict }) {
  const [layout, setLayout] = useState(() => normalizeLayout(initialLayout));
  const [saveStatus, setSaveStatus] = useState({ text: IDLE_STATUS_TEXT, isError: false });
  const layoutRef = useRef(layout);
  const timerRef = useRef(null);
  // antrean simpan: maksimal 1 request jalan. Ada perubahan pas request jalan -> isDirty, abis request selesai
  // langsung kirim snapshot TERBARU. Tanpa ini 2 request bisa jalan bareng & yg lama telat nyampe nimpa yg baru.
  const isSavingRef = useRef(false);
  const isDirtyRef = useRef(false);
  // nomor urut kiriman (naik terus). Kiriman pas halaman ditutup (keepalive) ga lewat antrean, jadi bisa aja
  // request lama nyampe belakangan: server bandingin sequence & ngabaiin yg lebih lama (POST /settings/table-layout)
  const clientIdRef = useRef(null);
  const sequenceRef = useRef(0);

  const postLayout = useCallback((isKeepalive) => {
    const { hidden_list: hiddenList, width_dict: widthDict } = layoutRef.current;
    if (clientIdRef.current === null) clientIdRef.current = createClientId();
    sequenceRef.current += 1;
    return postJson(layoutUrl, {
      table_key: tableKey,
      hidden_list: hiddenList,
      width_dict: widthDict,
      client_id: clientIdRef.current,
      sequence: sequenceRef.current,
    }, isKeepalive);
  }, [layoutUrl, tableKey]);

  const sendLayout = useCallback(async () => {
    timerRef.current = null;
    if (isSavingRef.current) {
      isDirtyRef.current = true;
      return;
    }
    isSavingRef.current = true;
    try {
      do {
        isDirtyRef.current = false;
        try {
          await postLayout(false);
          if (!isDirtyRef.current) {
            setSaveStatus({ text: "Table layout saved", isError: false });
            // pesan sukses ga masuk riwayat status bar biar ga numpuk tiap kolom digeser
            showStatus("Table layout saved", "success", false);
          }
        } catch (saveError) {
          const text = saveError.message || "Failed to save the table layout";
          setSaveStatus({ text, isError: true });
          showStatus(text, "danger");
        }
      } while (isDirtyRef.current);
    } finally {
      isSavingRef.current = false;
    }
  }, [postLayout]);

  const updateLayout = useCallback((nextLayout, { isSaved = true } = {}) => {
    layoutRef.current = nextLayout;
    setLayout(nextLayout);
    if (!isSaved) return;
    setSaveStatus({ text: "Saving layout...", isError: false });
    window.clearTimeout(timerRef.current);
    timerRef.current = window.setTimeout(() => sendLayout(), SAVE_DELAY_MS);
  }, [sendLayout]);

  // halaman ditutup / pindah pas ada perubahan yg belum kekirim -> langsung kirim snapshot terbaru (keepalive),
  // ga nunggu antrean karena halamannya udah mau ilang
  useEffect(() => {
    function flushPendingSave() {
      if (timerRef.current === null && !isDirtyRef.current) return;
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
      isDirtyRef.current = false;
      postLayout(true).catch(() => {});
    }
    window.addEventListener("pagehide", flushPendingSave);
    return () => {
      window.removeEventListener("pagehide", flushPendingSave);
      window.clearTimeout(timerRef.current);
    };
  }, [postLayout]);

  const isHidden = useCallback(
    (column) => column.is_hideable && layout.hidden_list.includes(column.key),
    [layout],
  );

  const getWidth = useCallback(
    (column) => layout.width_dict[column.key] || defaultWidthDict[column.key] || column.width,
    [layout, defaultWidthDict],
  );

  const setHidden = useCallback((key, hidden) => {
    const current = layoutRef.current;
    const hiddenList = current.hidden_list.filter((hiddenKey) => hiddenKey !== key);
    if (hidden) hiddenList.push(key);
    updateLayout({ ...current, hidden_list: hiddenList });
  }, [updateLayout]);

  // isSaved false = lagi digeser (cuma ganti tampilan), true = selesai geser (disimpen)
  const setWidth = useCallback((key, width, isSaved = true) => {
    const current = layoutRef.current;
    updateLayout({ ...current, width_dict: { ...current.width_dict, [key]: clampWidth(width) } }, { isSaved });
  }, [updateLayout]);

  // balikin ke layout awal: kolom bawaan, lebar bawaan
  const reset = useCallback(() => {
    updateLayout({ hidden_list: [...normalizeLayout(defaultLayout).hidden_list], width_dict: {} });
  }, [updateLayout, defaultLayout]);

  return { isHidden, getWidth, setHidden, setWidth, reset, saveStatus };
}
