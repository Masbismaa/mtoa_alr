// kriteria tabel disimpen sebagai object { key: [nilai, ...] } (bentuknya sama kayak "query" dari server),
// soalnya satu parameter bisa punya banyak nilai (Multi Selection: ?title=a&title=b).

// object kriteria + nomor halaman -> "title=a&title=b&page=2" (tanpa "?")
export function buildQueryText(query, page = 1) {
  const params = new URLSearchParams();
  Object.entries(query).forEach(([key, valueList]) => {
    valueList.forEach((value) => params.append(key, value));
  });
  if (page > 1) params.append("page", String(page));
  return params.toString();
}

// URL lengkap: base + ?query + #anchor (bagian yg kosong ga ditulis)
export function buildUrl(baseUrl, query, page = 1, anchor = "") {
  const queryText = buildQueryText(query, page);
  return baseUrl + (queryText ? "?" + queryText : "") + (anchor ? "#" + anchor : "");
}

// "?title=a&page=2" -> { query: { title: ["a"] }, page: 2 }. Dipake pas tombol Back/Forward browser
export function parseQueryText(search) {
  const params = new URLSearchParams(search);
  const query = {};
  let page = 1;
  params.forEach((value, key) => {
    if (key === "page") {
      const number = parseInt(value, 10);
      page = Number.isFinite(number) && number > 0 ? number : 1;
      return;
    }
    (query[key] = query[key] || []).push(value);
  });
  return { query, page };
}

// salinan kriteria dgn satu parameter diganti (nilai kosong = parameternya dibuang)
export function withQueryValue(query, key, value) {
  const nextQuery = { ...query };
  const cleanValue = (value || "").trim();
  if (cleanValue) nextQuery[key] = [cleanValue];
  else delete nextQuery[key];
  return nextQuery;
}
