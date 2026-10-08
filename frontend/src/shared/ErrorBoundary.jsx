// jaring pengaman: kalau ada error pas nampilin komponen, user dapet pesan + tombol muat ulang
// (bukan kartu kosong tanpa penjelasan). Detail error-nya ditulis di console browser buat developer.
import { Component } from "react";
import { reloadPage } from "./navigation.js";

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, info) {
    console.error("Komponen React ALR error:", error, info.componentStack);
  }

  render() {
    if (!this.state.hasError) return this.props.children;
    return (
      <div className="card-body">
        <div className="alert alert-danger m-0" role="alert">
          Tabel gagal ditampilkan.{" "}
          <button type="button" className="btn btn-sm ms-2" onClick={reloadPage}>Muat ulang</button>
        </div>
      </div>
    );
  }
}
