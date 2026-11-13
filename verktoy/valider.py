#!/usr/bin/env python3
"""Sjekker data.json før den committes.

Bruk:
  python3 verktoy/valider.py              sjekker data.json
  python3 verktoy/valider.py --staged     sjekker også at data.json er den eneste fila som er lagt til commit

Bare standardbiblioteket, så skriptet kjører hvor som helst uten installasjon.
Avslutter med kode 1 og en liste over feil hvis noe er galt.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROT = Path(__file__).resolve().parent.parent
DATA = ROT / "data.json"

STATUS = {"active", "paused", "planned", "idea", "done"}
RESERVERT = {"oversikt", "forelesninger", "timeplan", "settings", "sidebar", "customize", "upgrade", "downloads"}
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
DATO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DRIVE_ID = re.compile(r"^[A-Za-z0-9_-]{10,80}$")
TRYGG_LENKE = re.compile(r"^(https://|http://|mailto:)\S+$", re.I)
KONTROLLTEGN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

TOPP = {"title", "lede", "contact", "updated", "groups", "lectures"}
GRUPPE = {"id", "title", "note", "empty", "items"}
PROSJEKT = {"id", "code", "title", "status", "text", "tools", "more", "spec", "links"}

feil = []


def meld(sti, tekst):
    feil.append(f"{sti}: {tekst}")


def tekst(sti, v, maks, påkrevd=False):
    if not isinstance(v, str):
        meld(sti, "skal være tekst")
        return
    if påkrevd and not v.strip():
        meld(sti, "kan ikke være tom")
    if len(v) > maks:
        meld(sti, f"er {len(v)} tegn, maks er {maks}")
    if KONTROLLTEGN.search(v):
        meld(sti, "inneholder usynlige kontrolltegn")


def tekstliste(sti, v, maks_antall, maks_tegn):
    if not isinstance(v, list):
        meld(sti, "skal være en liste")
        return
    if len(v) > maks_antall:
        meld(sti, f"har {len(v)} punkter, maks er {maks_antall}")
    for i, x in enumerate(v):
        tekst(f"{sti}[{i}]", x, maks_tegn, påkrevd=True)


def par(sti, v, maks_antall, lenke=False):
    if not isinstance(v, list):
        meld(sti, "skal være en liste")
        return
    if len(v) > maks_antall:
        meld(sti, f"har {len(v)} punkter, maks er {maks_antall}")
    for i, p in enumerate(v):
        s = f"{sti}[{i}]"
        if not (isinstance(p, list) and len(p) == 2):
            meld(s, 'skal være et par: ["etikett", "verdi"]')
            continue
        tekst(f"{s}[0]", p[0], 40, påkrevd=True)
        if lenke:
            if not isinstance(p[1], str) or not TRYGG_LENKE.match(p[1].strip()):
                meld(f"{s}[1]", "lenken må starte med https://, http:// eller mailto:")
        else:
            tekst(f"{s}[1]", p[1], 600, påkrevd=True)


def ukjente(sti, obj, tillatt):
    for k in obj:
        if k not in tillatt:
            meld(sti, f"ukjent felt «{k}» (skrivefeil?)")


def sjekk_data(d):
    if not isinstance(d, dict):
        meld("data.json", "skal være et objekt")
        return
    ukjente("topp", d, TOPP)
    tekst("title", d.get("title"), 60, påkrevd=True)
    if "lede" in d:
        tekst("lede", d["lede"], 400)
    if "updated" in d and (not isinstance(d["updated"], str) or not DATO.match(d["updated"])):
        meld("updated", "skal være en dato som 2026-11-13")
    if "contact" in d:
        par("contact", d["contact"], 6, lenke=True)

    grupper = d.get("groups")
    if not isinstance(grupper, list) or not grupper:
        meld("groups", "skal være en liste med minst én gruppe")
        return

    gruppe_ider, prosjekt_ider = set(), set()
    for gi, g in enumerate(grupper):
        gs = f"groups[{gi}]"
        if not isinstance(g, dict):
            meld(gs, "skal være et objekt")
            continue
        ukjente(gs, g, GRUPPE)
        gid = g.get("id")
        if not isinstance(gid, str) or not SLUG.match(gid):
            meld(f"{gs}.id", "bare små bokstaver a–z, tall og bindestrek")
        elif gid in RESERVERT:
            meld(f"{gs}.id", f"«{gid}» er reservert av siden")
        elif gid in gruppe_ider:
            meld(f"{gs}.id", f"«{gid}» er brukt før")
        gruppe_ider.add(gid)
        tekst(f"{gs}.title", g.get("title"), 40, påkrevd=True)
        for k, maks in (("note", 300), ("empty", 200)):
            if k in g:
                tekst(f"{gs}.{k}", g[k], maks)

        items = g.get("items")
        if not isinstance(items, list):
            meld(f"{gs}.items", "skal være en liste")
            continue
        for ii, it in enumerate(items):
            s = f"{gs}.items[{ii}]"
            if not isinstance(it, dict):
                meld(s, "skal være et objekt")
                continue
            navn = it.get("id", "?")
            s = f"{gs}.items[{ii}] ({navn})"
            ukjente(s, it, PROSJEKT)
            pid = it.get("id")
            if not isinstance(pid, str) or not SLUG.match(pid):
                meld(f"{s}.id", "bare små bokstaver a–z, tall og bindestrek")
            elif pid in prosjekt_ider:
                meld(f"{s}.id", f"«{pid}» er brukt før")
            prosjekt_ider.add(pid)
            tekst(f"{s}.code", it.get("code"), 12, påkrevd=True)
            tekst(f"{s}.title", it.get("title"), 90, påkrevd=True)
            if it.get("status") not in STATUS:
                meld(f"{s}.status", f"må være en av {', '.join(sorted(STATUS))}")
            tekst(f"{s}.text", it.get("text", ""), 1200)
            tekstliste(f"{s}.tools", it.get("tools", []), 15, 40)
            tekstliste(f"{s}.more", it.get("more", []), 10, 400)
            par(f"{s}.spec", it.get("spec", []), 8)
            par(f"{s}.links", it.get("links", []), 6, lenke=True)
            if not it.get("text") and not it.get("spec"):
                meld(s, "trenger enten text eller spec, ellers står prosjektet tomt")

    lek = d.get("lectures")
    if lek is not None:
        if not isinstance(lek, dict) or not isinstance(lek.get("courses"), list):
            meld("lectures", "skal ha en liste «courses»")
        else:
            for ci, c in enumerate(lek["courses"]):
                cs = f"lectures.courses[{ci}]"
                if not isinstance(c, dict):
                    meld(cs, "skal være et objekt")
                    continue
                if not isinstance(c.get("folder"), str) or not DRIVE_ID.match(c["folder"]):
                    meld(f"{cs}.folder", "ser ikke ut som en Drive-ID")
                for liste in ("items", "extra"):
                    for xi, x in enumerate(c.get(liste) or []):
                        if not isinstance(x, dict) or not isinstance(x.get("file"), str) or not DRIVE_ID.match(x["file"]):
                            meld(f"{cs}.{liste}[{xi}].file", "ser ikke ut som en Drive-ID")


def sjekk_staged():
    try:
        ut = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=ROT,
                            capture_output=True, text=True, check=True).stdout.split()
    except (OSError, subprocess.CalledProcessError) as e:
        meld("git", f"fikk ikke lest hva som er lagt til commit ({e})")
        return
    andre = [f for f in ut if f != "data.json"]
    if andre:
        meld("commit", "agenten skal bare committe data.json, men disse er også lagt til: " + ", ".join(andre))
    if "data.json" not in ut:
        meld("commit", "data.json er ikke lagt til commit")


def main():
    try:
        d = json.loads(DATA.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print("Fant ikke data.json", file=sys.stderr)
        return 1
    except json.JSONDecodeError as e:
        print(f"data.json er ikke gyldig JSON: linje {e.lineno}, kolonne {e.colno}: {e.msg}", file=sys.stderr)
        return 1
    sjekk_data(d)
    if "--staged" in sys.argv:
        sjekk_staged()
    if feil:
        print(f"{len(feil)} feil i data.json:", file=sys.stderr)
        for f in feil:
            print("  - " + f, file=sys.stderr)
        return 1
    antall = sum(len(g.get("items", [])) for g in d["groups"])
    print(f"data.json er gyldig: {len(d['groups'])} grupper, {antall} prosjekter.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
