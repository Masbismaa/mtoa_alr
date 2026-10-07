"""Pengaman bawaan cek link (anti SSRF), ga perlu disetting: alamat berbahaya selalu ditolak."""
import ipaddress
import socket
from collections import namedtuple
from urllib.parse import urlsplit
from flask import current_app, has_app_context

# URL yg udah dibongkar: dipake buat konek ke IP yg udah dicek
ParsedCheckUrl = namedtuple("ParsedCheckUrl", ["scheme", "hostname", "port", "request_path"])

DEFAULT_PORT_DICT = {"http": 80, "https": 443}

# alamat yg ga boleh didatengin server: dirinya sendiri, metadata cloud, multicast, dll
FORBIDDEN_NETWORK_LIST = [
    ipaddress.ip_network(network_text) for network_text in (
        "0.0.0.0/8", "127.0.0.0/8", "169.254.0.0/16", "224.0.0.0/4", "240.0.0.0/4", "255.255.255.255/32",
        "100.64.0.0/10", "::/128", "::1/128", "fe80::/10", "ff00::/8", "2002::/16", "2001::/32",
    )
]

class LinkTargetBlockedError(Exception):
    """Target termasuk alamat terlarang / URL-nya ga valid. Pesannya aman buat ditampilin."""

def unwrap_ip(ip):
    """IPv6 yg isinya IPv4 (::ffff:127.0.0.1) dibuka jadi IPv4 aslinya, biar ga bisa dipake nyelundupin loopback."""
    if ip.version == 6 and ip.ipv4_mapped is not None:
        return ip.ipv4_mapped
    return ip

def is_forbidden_ip(ip, allow_private=False):
    """True kalau IP termasuk loopback, link-local, multicast, unspecified, atau reserved."""
    ip = unwrap_ip(ip)
    return (
        ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified or ip.is_reserved
        or any(ip.version == network.version and ip in network for network in FORBIDDEN_NETWORK_LIST)
        or (not allow_private and not ip.is_global)
    )

def resolve_host_ip_list(host, port):
    """IP langsung dipake apa adanya, hostname ditanyain ke DNS dulu."""
    try:
        return [ipaddress.ip_address(host)]
    except ValueError:
        pass
    ip_list = []
    for info in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM):
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        if ip not in ip_list:
            ip_list.append(ip)
    return ip_list

def resolve_safe_ip(host, port, allow_private=None):
    """Cek semua IP tujuan. Satu aja terlarang langsung ditolak. Balikin IP yg dipake konek (dikunci, anti DNS rebinding)."""
    clean_host = (host or "").strip().lower().rstrip(".")
    if not clean_host:
        raise LinkTargetBlockedError("Alamat kosong")
    ip_list = resolve_host_ip_list(clean_host, port)
    if not ip_list:
        raise LinkTargetBlockedError("Alamat tidak ditemukan")
    if allow_private is None:
        allow_private = has_app_context() and current_app.config["LINK_CHECK_ALLOW_PRIVATE_NETWORKS"]
    for ip in ip_list:
        if is_forbidden_ip(ip, allow_private):
            raise LinkTargetBlockedError(f"IP {unwrap_ip(ip)} termasuk alamat terlarang")
    return str(unwrap_ip(ip_list[0]))

def parse_check_url(url):
    """Bongkar URL. Cuma http/https, tanpa username:password di URL."""
    try:
        parts = urlsplit((url or "").strip())
        port = parts.port
    except ValueError as error:
        raise LinkTargetBlockedError("Format URL tidak valid") from error
    scheme = parts.scheme.lower()
    if scheme not in DEFAULT_PORT_DICT:
        raise LinkTargetBlockedError("URL harus diawali http:// atau https://")
    if parts.username or parts.password:
        raise LinkTargetBlockedError("URL berisi username/password tidak diizinkan")
    if not parts.hostname:
        raise LinkTargetBlockedError("Format URL tidak valid")
    request_path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
    return ParsedCheckUrl(scheme, parts.hostname, port or DEFAULT_PORT_DICT[scheme], request_path)
