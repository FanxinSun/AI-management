// Fast native Win32 wl-paste bridge for WSL2 (agy / claude / codex / Wayland CLI tools).
// Reads images (raw PNG, DIB/Bitmap via GDI+, JPEG, GIF, WebP), copied files (CF_HDROP ->
// file:// WSL paths), and UTF-8 text directly from the Windows clipboard in ~30ms.

#define WIN32_LEAN_AND_MEAN
#define UNICODE
#define _UNICODE
#include <windows.h>
#include <shellapi.h>
#include <objidl.h>
#include <gdiplus.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <io.h>
#include <fcntl.h>

#pragma comment(lib, "user32.lib")
#pragma comment(lib, "gdiplus.lib")
#pragma comment(lib, "shell32.lib")
#pragma comment(lib, "ole32.lib")

static bool open_clipboard_retry(void) {
    for (int i = 0; i < 15; i++) {
        if (OpenClipboard(NULL)) return true;
        Sleep(10);
    }
    return false;
}

static size_t exact_png_size(const unsigned char* p, size_t max_sz) {
    static const unsigned char sig[8] = {0x89, 'P', 'N', 'G', 0x0D, 0x0A, 0x1A, 0x0A};
    if (max_sz < 8 || memcmp(p, sig, 8) != 0) return 0;
    size_t pos = 8;
    while (pos + 12 <= max_sz) {
        unsigned int len = ((unsigned int)p[pos] << 24) |
                           ((unsigned int)p[pos + 1] << 16) |
                           ((unsigned int)p[pos + 2] << 8) |
                           ((unsigned int)p[pos + 3]);
        if (len > max_sz - pos - 12) return max_sz;
        const unsigned char* type = p + pos + 4;
        pos += 12 + (size_t)len;
        if (memcmp(type, "IEND", 4) == 0) {
            return pos;
        }
    }
    return max_sz;
}

static bool write_raw_format(UINT cf, bool trim_png) {
    if (!cf || !IsClipboardFormatAvailable(cf)) return false;
    HANDLE h = GetClipboardData(cf);
    if (!h) return false;
    SIZE_T sz = GlobalSize(h);
    const unsigned char* p = (const unsigned char*)GlobalLock(h);
    if (!p || sz == 0) {
        if (p) GlobalUnlock(h);
        return false;
    }
    size_t out_sz = (size_t)sz;
    if (trim_png) {
        size_t png_sz = exact_png_size(p, out_sz);
        if (png_sz == 0) {
            GlobalUnlock(h);
            return false;
        }
        out_sz = png_sz;
    }
    bool ok = (fwrite(p, 1, out_sz, stdout) == out_sz);
    GlobalUnlock(h);
    return ok;
}

static bool write_bitmap_as_png(void) {
    HBITMAP hbm = (HBITMAP)GetClipboardData(CF_BITMAP);
    if (!hbm) return false;

    Gdiplus::GdiplusStartupInput gsi;
    ULONG_PTR token = 0;
    if (Gdiplus::GdiplusStartup(&token, &gsi, NULL) != Gdiplus::Ok) return false;

    bool ok = false;
    {
        Gdiplus::Bitmap* bmp = Gdiplus::Bitmap::FromHBITMAP(hbm, NULL);
        if (bmp && bmp->GetLastStatus() == Gdiplus::Ok) {
            IStream* stream = NULL;
            if (SUCCEEDED(CreateStreamOnHGlobal(NULL, TRUE, &stream)) && stream) {
                static const CLSID clsidPng = {
                    0x557cf406, 0x1a04, 0x11d3,
                    {0x9a, 0x73, 0x00, 0x00, 0xf8, 0x1e, 0xf3, 0x2e}
                };
                if (bmp->Save(stream, &clsidPng, NULL) == Gdiplus::Ok) {
                    STATSTG st = {};
                    HGLOBAL hg = NULL;
                    if (SUCCEEDED(stream->Stat(&st, STATFLAG_NONAME)) &&
                        SUCCEEDED(GetHGlobalFromStream(stream, &hg)) && hg) {
                        const void* data = GlobalLock(hg);
                        if (data && st.cbSize.QuadPart > 0) {
                            size_t n = (size_t)st.cbSize.QuadPart;
                            ok = (fwrite(data, 1, n, stdout) == n);
                            GlobalUnlock(hg);
                        }
                    }
                }
                stream->Release();
            }
        }
        delete bmp;
    }
    Gdiplus::GdiplusShutdown(token);
    return ok;
}

static void print_percent_encoded_path(const char* linux_path) {
    fputs("file://", stdout);
    for (const unsigned char* s = (const unsigned char*)linux_path; *s; ++s) {
        unsigned char c = *s;
        if ((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') ||
            (c >= '0' && c <= '9') || c == '-' || c == '.' ||
            c == '_' || c == '~' || c == '/') {
            fputc(c, stdout);
        } else {
            fprintf(stdout, "%%%02X", c);
        }
    }
    fputc('\n', stdout);
}

static bool write_uri_list(void) {
    if (!IsClipboardFormatAvailable(CF_HDROP)) return false;
    HDROP hDrop = (HDROP)GetClipboardData(CF_HDROP);
    if (!hDrop) return false;

    char distro[128] = "Ubuntu";
    DWORD dlen = GetEnvironmentVariableA("WSL_DISTRO_NAME", distro, sizeof(distro));
    if (dlen == 0 || dlen >= sizeof(distro)) strcpy_s(distro, "Ubuntu");

    UINT count = DragQueryFileW(hDrop, 0xFFFFFFFF, NULL, 0);
    if (count == 0) return false;

    bool any = false;
    WCHAR wpath[4096];
    char utf8[12288];
    char converted[12300];

    for (UINT i = 0; i < count; i++) {
        if (DragQueryFileW(hDrop, i, wpath, 4096) == 0) continue;
        int n = WideCharToMultiByte(CP_UTF8, 0, wpath, -1, utf8, sizeof(utf8), NULL, NULL);
        if (n <= 1) continue;
        for (char* p = utf8; *p; ++p) {
            if (*p == '\\') *p = '/';
        }
        if (isalpha((unsigned char)utf8[0]) && utf8[1] == ':' && utf8[2] == '/') {
            snprintf(converted, sizeof(converted), "/mnt/%c/%s",
                     tolower((unsigned char)utf8[0]), utf8 + 3);
            print_percent_encoded_path(converted);
            any = true;
        } else {
            const char* prefixes[2] = {"//wsl.localhost/", "//wsl$/"};
            bool matched = false;
            for (int k = 0; k < 2; k++) {
                size_t plen = strlen(prefixes[k]);
                if (_strnicmp(utf8, prefixes[k], plen) == 0) {
                    const char* rest = utf8 + plen;
                    size_t d_len = strlen(distro);
                    if (_strnicmp(rest, distro, d_len) == 0 && rest[d_len] == '/') {
                        print_percent_encoded_path(rest + d_len);
                        any = true;
                        matched = true;
                        break;
                    }
                }
            }
            if (!matched && utf8[0] == '/') {
                print_percent_encoded_path(utf8);
                any = true;
            }
        }
    }
    return any;
}

static bool write_text_utf8(bool no_newline) {
    if (!IsClipboardFormatAvailable(CF_UNICODETEXT)) return false;
    HANDLE h = GetClipboardData(CF_UNICODETEXT);
    if (!h) return false;
    const WCHAR* wp = (const WCHAR*)GlobalLock(h);
    if (!wp) return false;

    size_t max_chars = GlobalSize(h) / sizeof(WCHAR);
    size_t wlen = 0;
    while (wlen < max_chars && wp[wlen] != L'\0') wlen++;

    bool ok = true;
    if (wlen > 0) {
        int needed = WideCharToMultiByte(CP_UTF8, 0, wp, (int)wlen, NULL, 0, NULL, NULL);
        if (needed > 0) {
            char* buf = (char*)malloc((size_t)needed);
            if (buf) {
                int written = WideCharToMultiByte(CP_UTF8, 0, wp, (int)wlen, buf, needed, NULL, NULL);
                // Normalize CRLF -> LF for Linux tools
                size_t out_idx = 0;
                for (int i = 0; i < written; i++) {
                    if (buf[i] == '\r' && i + 1 < written && buf[i + 1] == '\n') continue;
                    buf[out_idx++] = buf[i];
                }
                if (out_idx > 0) {
                    ok = (fwrite(buf, 1, out_idx, stdout) == out_idx);
                }
                free(buf);
            }
        }
    }
    GlobalUnlock(h);
    if (ok && !no_newline) {
        fputc('\n', stdout);
    }
    return ok;
}

int main(int argc, char** argv) {
    _setmode(_fileno(stdout), _O_BINARY);
    _setmode(_fileno(stderr), _O_BINARY);

    bool list_types = false;
    bool no_newline = false;
    const char* req_type = NULL;

    for (int i = 1; i < argc; i++) {
        const char* a = argv[i];
        if (strcmp(a, "-l") == 0 || strcmp(a, "--list-types") == 0) {
            list_types = true;
        } else if (strcmp(a, "-n") == 0 || strcmp(a, "--no-newline") == 0) {
            no_newline = true;
        } else if (strcmp(a, "-p") == 0 || strcmp(a, "--primary") == 0) {
            // Windows has a single system clipboard; accept cleanly.
        } else if (strcmp(a, "-t") == 0 || strcmp(a, "--type") == 0) {
            if (i + 1 < argc) req_type = argv[++i];
        } else if (strncmp(a, "--type=", 7) == 0) {
            req_type = a + 7;
        } else if (strncmp(a, "-t", 2) == 0 && a[2] != '\0') {
            req_type = a + 2;
        } else if (strcmp(a, "-s") == 0 || strcmp(a, "--seat") == 0) {
            if (i + 1 < argc) i++;
        } else if (strncmp(a, "--seat=", 7) == 0) {
            // ignore seat
        } else if (strcmp(a, "-v") == 0 || strcmp(a, "--version") == 0) {
            fputs("wl-paste (wsl-winclip) 2.2.1\n", stdout);
            return 0;
        } else if (strcmp(a, "-h") == 0 || strcmp(a, "--help") == 0) {
            fputs("Usage: wl-paste [--list-types] [--type MIME] [--no-newline]\n", stdout);
            return 0;
        }
    }

    if (!open_clipboard_retry()) {
        fputs("Nothing is copied\n", stderr);
        return 1;
    }

    UINT cf_png      = RegisterClipboardFormatW(L"PNG");
    UINT cf_mime_png = RegisterClipboardFormatW(L"image/png");
    UINT cf_jfif     = RegisterClipboardFormatW(L"JFIF");
    UINT cf_mime_jpg = RegisterClipboardFormatW(L"image/jpeg");
    UINT cf_gif      = RegisterClipboardFormatW(L"GIF");
    UINT cf_mime_gif = RegisterClipboardFormatW(L"image/gif");
    UINT cf_webp     = RegisterClipboardFormatW(L"image/webp");

    bool has_hdrop = IsClipboardFormatAvailable(CF_HDROP) != 0;
    bool has_png_raw = (cf_png && IsClipboardFormatAvailable(cf_png)) ||
                       (cf_mime_png && IsClipboardFormatAvailable(cf_mime_png));
    bool has_dib = IsClipboardFormatAvailable(CF_BITMAP) ||
                   IsClipboardFormatAvailable(CF_DIB) ||
                   IsClipboardFormatAvailable(CF_DIBV5);
    bool has_jpg = (cf_jfif && IsClipboardFormatAvailable(cf_jfif)) ||
                   (cf_mime_jpg && IsClipboardFormatAvailable(cf_mime_jpg));
    bool has_gif = (cf_gif && IsClipboardFormatAvailable(cf_gif)) ||
                   (cf_mime_gif && IsClipboardFormatAvailable(cf_mime_gif));
    bool has_webp = (cf_webp && IsClipboardFormatAvailable(cf_webp));
    bool has_text = IsClipboardFormatAvailable(CF_UNICODETEXT) != 0;

    if (!has_hdrop && !has_png_raw && !has_dib && !has_jpg && !has_gif && !has_webp && !has_text) {
        CloseClipboard();
        fputs("Nothing is copied\n", stderr);
        return 1;
    }

    if (list_types) {
        if (has_hdrop) fputs("text/uri-list\n", stdout);
        if (has_png_raw || has_dib) fputs("image/png\n", stdout);
        if (has_jpg) fputs("image/jpeg\n", stdout);
        if (has_gif) fputs("image/gif\n", stdout);
        if (has_webp) fputs("image/webp\n", stdout);
        if (has_text) {
            fputs("text/plain;charset=utf-8\n", stdout);
            fputs("text/plain\n", stdout);
            fputs("UTF8_STRING\n", stdout);
            fputs("TEXT\n", stdout);
            fputs("STRING\n", stdout);
        }
        CloseClipboard();
        fflush(stdout);
        return 0;
    }

    bool ok = false;
    if (!req_type) {
        if (has_text) {
            ok = write_text_utf8(no_newline);
        } else if (has_hdrop) {
            ok = write_uri_list();
        }
    } else if (strcmp(req_type, "text/uri-list") == 0) {
        ok = write_uri_list();
    } else if (strncmp(req_type, "image/png", 9) == 0) {
        if (cf_png && IsClipboardFormatAvailable(cf_png)) {
            ok = write_raw_format(cf_png, true);
        }
        if (!ok && cf_mime_png && IsClipboardFormatAvailable(cf_mime_png)) {
            ok = write_raw_format(cf_mime_png, true);
        }
        if (!ok && has_dib) {
            ok = write_bitmap_as_png();
        }
    } else if (strncmp(req_type, "image/jpeg", 10) == 0 || strcmp(req_type, "image/jpg") == 0) {
        ok = write_raw_format(cf_jfif, false) || write_raw_format(cf_mime_jpg, false);
    } else if (strncmp(req_type, "image/gif", 9) == 0) {
        ok = write_raw_format(cf_gif, false) || write_raw_format(cf_mime_gif, false);
    } else if (strncmp(req_type, "image/webp", 10) == 0) {
        ok = write_raw_format(cf_webp, false);
    } else if (strncmp(req_type, "text/", 5) == 0 ||
               strcmp(req_type, "UTF8_STRING") == 0 ||
               strcmp(req_type, "STRING") == 0 ||
               strcmp(req_type, "TEXT") == 0) {
        ok = write_text_utf8(no_newline);
    }

    CloseClipboard();
    fflush(stdout);
    if (!ok) {
        fputs("Clipboard content is not available as requested type\n", stderr);
        return 1;
    }
    return 0;
}
