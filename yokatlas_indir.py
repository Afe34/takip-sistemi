#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YKS Sistemim · YÖK Atlas Sayısal Veri Dönüştürücü & Çekici
----------------------------------------------------------
Ürettiği `yokatlas-sayisal.json` dosyasını GitHub reponda `index.html`
dosyasının hemen yanına koyduğunda uygulama tüm Sayısal programları
otomatik olarak yükler.

Kullanım:
  1) YÖK Atlas'tan indirdiğin Excel/CSV/HTML dosyasını dönüştürmek (ÖNERİLEN):
       python yokatlas_indir.py indirilen_dosya.xlsx
       python yokatlas_indir.py indirilen_dosya.csv

  2) `yokatlas-py` paketi kuruluysa doğrudan YÖK Atlas'tan çekmeyi denemek:
       pip install yokatlas-py
       python yokatlas_indir.py --cek
"""

import csv
import html
import json
import os
import re
import sys
from datetime import date

NET_KEYS = [
    ("tyt_tr",  [r"tyt.*turk", r"^tyt_tr$"]),
    ("tyt_sos", [r"tyt.*sos",  r"^tyt_sos$"]),
    ("tyt_mat", [r"tyt.*mat",  r"^tyt_mat$"]),
    ("tyt_fen", [r"tyt.*fen",  r"^tyt_fen$"]),
    ("ayt_mat", [r"ayt.*mat",  r"^ayt_mat$"]),
    ("ayt_fiz", [r"ayt.*fiz",  r"^ayt_fiz$"]),
    ("ayt_kim", [r"ayt.*kim",  r"^ayt_kim$"]),
    ("ayt_bio", [r"ayt.*biy",  r"ayt.*bio", r"^ayt_bio$"]),
]


def norm_tr(text):
    s = str(text or "")
    for a, b in [("İ", "i"), ("I", "i"), ("ı", "i"), ("Ş", "s"), ("ş", "s"),
                 ("Ğ", "g"), ("ğ", "g"), ("Ü", "u"), ("ü", "u"),
                 ("Ö", "o"), ("ö", "o"), ("Ç", "c"), ("ç", "c")]:
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s.lower()).strip()


def parse_num(val):
    if val is None or isinstance(val, bool):
        return None
    if isinstance(val, (int, float)):
        return float(val) if val == val else None
    s = str(val).strip()
    if not s or re.match(r"^(-+|dolmad|yeni|yok|--)$", s, re.I):
        return None
    s = re.sub(r"\s+", "", s)
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    elif re.match(r"^\d{1,3}(\.\d{3})+$", s):
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def strip_tags(s):
    return html.unescape(re.sub(r"<[^>]+>", " ", str(s or ""))).strip()


def normalize_record(raw):
    code = re.sub(r"\D", "", str(raw.get("code") or ""))
    uni = str(raw.get("uni") or "").strip()
    dept = str(raw.get("dept") or "").strip()
    if not uni and not dept:
        return None
    if not code and uni:
        m = re.search(r"\b(\d{9})\b", uni)
        if m:
            code = m.group(1)

    city = str(raw.get("city") or "").strip()
    ut_raw = str(raw.get("uniType") or "").strip()
    if re.search(r"vak[ıi]f", ut_raw, re.I):
        uni_type = "Vakıf"
    elif re.search(r"kktc", ut_raw, re.I):
        uni_type = "KKTC"
    elif re.search(r"yurt", ut_raw, re.I):
        uni_type = "Yurt Dışı"
    else:
        uni_type = ut_raw or "Devlet"

    fee_raw = str(raw.get("fee") or "").strip()
    if fee_raw:
        fee = fee_raw
    elif re.search(r"burslu", dept, re.I):
        fee = "Burslu"
    elif "%50" in dept:
        fee = "%50 İndirimli"
    elif "%25" in dept:
        fee = "%25 İndirimli"
    elif re.search(r"ücretli|ucretli", dept, re.I):
        fee = "Ücretli"
    else:
        fee = "Ücretsiz" if uni_type == "Devlet" else "Ücretli"

    rank_n = parse_num(raw.get("rank"))
    score_n = parse_num(raw.get("score"))
    rec = {
        "code": code,
        "uni": uni,
        "dept": dept,
        "city": city,
        "uniType": uni_type,
        "fee": fee,
        "rank": int(round(rank_n)) if rank_n and rank_n > 0 else None,
        "score": round(score_n, 2) if score_n and score_n > 0 else None,
        "quota": str(raw.get("quota") or "").strip(),
    }
    if raw.get("year"):
        rec["year"] = str(raw["year"]).strip()
    if isinstance(raw.get("nets"), dict) and raw["nets"]:
        rec["nets"] = raw["nets"]
    return rec


def map_rows(rows):
    if not rows or len(rows) < 2:
        return []
    head_re = re.compile(r"universite|program|bolum|sehir|siralama|taban|kontenjan|ucret|burs|kodu|tbs")
    head_idx, best = 0, -1
    for i, r in enumerate(rows[:10]):
        sc = sum(1 for c in r if head_re.search(norm_tr(c)))
        if sc > best:
            best, head_idx = sc, i

    headers = [norm_tr(c) for c in rows[head_idx]]

    def find_col(patterns):
        for p in patterns:
            rx = re.compile(p)
            for idx, h in enumerate(headers):
                if rx.search(h):
                    return idx
        return -1

    c_code = find_col([r"program.*kod|yop.*kod|^kod$|^code$"])
    c_uni = find_col([r"universite|^uni$"])
    c_dept = find_col([r"program.*ad|bolum|program|^dept$"])
    c_city = find_col([r"sehir|^il$|^city$"])
    c_type = find_col([r"universite.*tur|^tur$|^unitype$"])
    c_fee = find_col([r"ucret|burs|^fee$"])
    c_quota = find_col([r"kontenjan|^quota$"])
    c_rank = find_col([r"tbs|siralama|basari.*sira|^rank$"])
    c_score = find_col([r"taban.*puan|en.*kucuk.*puan|^puan$|^score$"])
    c_pt = find_col([r"puan.*tur"])
    c_nets = {k: find_col(pats) for k, pats in NET_KEYS}

    out = []
    for r in rows[head_idx + 1:]:
        if not r or not any(str(c or "").strip() for c in r):
            continue
        get = lambda idx: r[idx] if 0 <= idx < len(r) else ""
        if c_pt >= 0:
            pt = norm_tr(get(c_pt))
            if pt and "say" not in pt:
                continue
        nets = {}
        for k, idx in c_nets.items():
            if idx >= 0:
                nv = parse_num(get(idx))
                if nv is not None and nv >= 0:
                    nets[k] = round(nv, 2)
        rec = normalize_record({
            "code": get(c_code),
            "uni": get(c_uni),
            "dept": get(c_dept),
            "city": get(c_city),
            "uniType": get(c_type),
            "fee": get(c_fee),
            "quota": get(c_quota),
            "rank": get(c_rank),
            "score": get(c_score),
            "nets": nets or None,
        })
        if rec:
            out.append(rec)
    return out


def convert_file(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xls"):
        try:
            import openpyxl
        except ImportError:
            sys.exit("Excel dosyası için önce şunu kur: pip install openpyxl")
        wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
        ws = wb.active
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
        return map_rows(rows)
    elif ext in (".html", ".htm"):
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            txt = f.read()
        rows = []
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", txt, re.I | re.S):
            cells = [strip_tags(c) for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr, re.I | re.S)]
            if cells:
                rows.append(cells)
        return map_rows(rows)
    elif ext == ".json":
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        arr = raw if isinstance(raw, list) else raw.get("programs", [])
        return [x for x in (normalize_record(r) for r in arr) if x]
    else:
        with open(path, "r", encoding="utf-8-sig", errors="ignore") as f:
            sample = f.read(4096)
            f.seek(0)
            delim = ";" if sample.count(";") > sample.count(",") else ("\t" if sample.count("\t") > sample.count(",") else ",")
            rows = list(csv.reader(f, delimiter=delim))
        return map_rows(rows)


def fetch_from_yokatlas():
    try:
        from yokatlas_py import search_lisans_programs
    except ImportError:
        sys.exit(
            "Doğrudan çekmek için `yokatlas-py` paketi gerekli:\n"
            "  pip install yokatlas-py\n\n"
            "Ya da YÖK Atlas Tercih Sihirbazı'ndan Excel/CSV indirip şunu çalıştırabilirsin:\n"
            "  python yokatlas_indir.py indirilen_dosya.xlsx"
        )

    print("YÖK Atlas Sayısal lisans programları çekiliyor (biraz sürebilir)...")
    res = search_lisans_programs({"puan_turu": "say", "length": 10000})
    items = res if isinstance(res, list) else (res.get("data") or res.get("results") or [])
    out = []
    for item in items:
        if not isinstance(item, dict):
            continue
        rec = normalize_record({
            "code": item.get("yop_kodu") or item.get("program_kodu") or item.get("code"),
            "uni": item.get("uni_adi") or item.get("universite") or item.get("uni"),
            "dept": item.get("program_adi") or item.get("bolum") or item.get("program"),
            "city": item.get("sehir_adi") or item.get("sehir") or item.get("city"),
            "uniType": item.get("uni_turu") or item.get("universite_turu"),
            "fee": item.get("ucret_burs") or item.get("ucret"),
            "quota": item.get("kontenjan") or "",
            "rank": item.get("tbs") or item.get("siralama"),
            "score": item.get("taban") or item.get("taban_puan"),
        })
        if rec:
            out.append(rec)
    return out


def save_output(programs, out_path="yokatlas-sayisal.json"):
    programs.sort(key=lambda x: (x["rank"] or 9999999, x["uni"], x["dept"]))
    payload = {
        "updatedAt": date.today().isoformat(),
        "count": len(programs),
        "programs": programs,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    kb = os.path.getsize(out_path) / 1024
    print(f"Hazır: {out_path} ({len(programs)} Sayısal program, {kb:.1f} KB)")
    print("Bu dosyayı GitHub reponda index.html yanına yüklemen yeterli.")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    arg = sys.argv[1]
    if arg == "--cek":
        progs = fetch_from_yokatlas()
    else:
        if not os.path.exists(arg):
            sys.exit(f"Dosya bulunamadı: {arg}")
        progs = convert_file(arg)
    if not progs:
        sys.exit("Hiç geçerli Sayısal program bulunamadı.")
    out_file = sys.argv[2] if len(sys.argv) > 2 else "yokatlas-sayisal.json"
    save_output(progs, out_file)


if __name__ == "__main__":
    main()
