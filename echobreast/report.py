"""Fiche de synthèse PDF (F9). Aucune donnée d'identité."""
from __future__ import annotations

import datetime as dt
import io

from fpdf import FPDF
from PIL import Image

from .core import CLASSES, LEVELS

ROSE = (142, 29, 74)
DISCLAIMER = ("Outil d'information et d'orientation, pas un diagnostic. Prototype de hackathon non valide "
              "cliniquement, entraine sur un jeu public (BUSI, Egypte) : performances non verifiees sur la "
              "population locale. La decision appartient au professionnel de sante.")


def _latin1(text: str) -> str:
    rep = {"≥": ">=", "≤": "<=", "—": "-", "–": "-", "’": "'", "«": '"', "»": '"', "×": "x", "…": "..."}
    for a, b in rep.items():
        text = text.replace(a, b)
    return text.encode("latin-1", "replace").decode("latin-1")


def build_pdf(annotated: Image.Image, result, model_version: str, case_name: str = "examen",
              annotations: list[dict] | None = None, decision: dict | None = None) -> bytes:
    """decision : {"relu", "complement", "prelevement": bool, "comment": str}, rempli dans l'application.
    Les cases non cochées et un commentaire vide restent à compléter à la main."""
    lv = LEVELS[result.level]
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(True, 15)
    pdf.add_page()
    pdf.set_fill_color(*ROSE)
    pdf.rect(0, 0, 210, 22, "F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_xy(12, 6)
    pdf.cell(0, 10, _latin1("EchoBreast - Fiche de synthèse"))
    pdf.set_text_color(40, 40, 40)

    pdf.set_xy(12, 28)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, _latin1(f"Référence : {case_name}   |   Date : {dt.datetime.now():%d/%m/%Y %H:%M}   |   "
                           f"Version du modèle : {model_version}"), new_x="LMARGIN", new_y="NEXT")

    buf = io.BytesIO()
    im = annotated.convert("RGB")
    im.thumbnail((900, 900))
    im.save(buf, format="PNG")
    buf.seek(0)
    pdf.image(buf, x=12, y=38, w=95)

    x0 = 115
    pdf.set_xy(x0, 38)
    r, g, b = (int(lv["color"][i:i + 2], 16) for i in (1, 3, 5))
    pdf.set_fill_color(r, g, b)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(83, 11, _latin1(f"  Niveau : {result.level.upper()} - {lv['label']}"), fill=True,
             new_x="LEFT", new_y="NEXT")
    pdf.set_text_color(40, 40, 40)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_x(x0)
    pdf.multi_cell(83, 5, _latin1(lv["text"]), align="L", new_x="LEFT", new_y="NEXT")
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_x(x0)
    pdf.cell(83, 7, _latin1("Ce que le modèle voit dans l'image"), new_x="LEFT", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    for name, p in zip(CLASSES, result.probs):
        pdf.set_x(x0)
        pdf.cell(30, 6, _latin1(name.capitalize()))
        pdf.set_fill_color(252, 228, 236)
        pdf.cell(40, 6, "", border=1)
        pdf.set_fill_color(*ROSE)
        pdf.set_x(x0 + 30)
        pdf.cell(max(0.5, 40 * float(p)), 6, "", fill=True)
        pdf.set_x(x0 + 72)
        pdf.cell(11, 6, f"{p:.0%}", new_x="LEFT", new_y="NEXT")
        pdf.set_x(x0)
    pdf.ln(2)
    pdf.set_x(x0)
    pdf.set_font("Helvetica", "I", 9)
    for reason in result.reasons + result.warnings:
        pdf.set_x(x0)
        pdf.multi_cell(83, 4.5, _latin1("- " + reason), align="L", new_x="LEFT", new_y="NEXT")
    pdf.set_x(x0)
    pdf.multi_cell(83, 4.5, _latin1("Contour de l'IA (étiquette « IA ») : " + ("lésion repérée, tracée dans la couleur du niveau"
                                    if result.mask is not None else "aucun contour")), align="L", new_x="LEFT", new_y="NEXT")
    if annotations:
        pdf.ln(2)
        pdf.set_x(x0)
        pdf.set_font("Helvetica", "B", 10)
        pdf.multi_cell(83, 5, _latin1("Zones ajoutées par le professionnel (étiquette « Soignant »)"), align="L",
                       new_x="LEFT", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        for i, a in enumerate(annotations, 1):
            pdf.set_x(x0)
            pdf.cell(83, 5, _latin1(f"Soignant {i} : {LEVELS[a['level']]['label']}"), new_x="LEFT", new_y="NEXT")

    pdf.set_xy(12, max(pdf.get_y(), 140) + 6)
    pdf.set_font("Helvetica", "B", 11)
    d = decision or {}
    filled = any(d.get(k) for k in ("relu", "complement", "prelevement", "comment"))
    pdf.cell(0, 7, _latin1("Décision du professionnel " + ("(renseignée dans EchoBreast, à compléter si besoin)"
                                                             if filled else "(à compléter à la main)")),
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    for k, label in (("relu", "Relecture effectuée"), ("complement", "Examen complémentaire demandé"),
                     ("prelevement", "Prélèvement indiqué")):
        pdf.cell(0, 7, _latin1(("[X] " if d.get(k) else "[ ] ") + label), new_x="LMARGIN", new_y="NEXT")
    comment = (d.get("comment") or "").strip()
    if comment:
        pdf.multi_cell(0, 6, _latin1("Commentaire : " + comment[:400]), align="L", new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.cell(0, 7, "Commentaire : ....................................................", new_x="LMARGIN", new_y="NEXT")

    pdf.set_y(-38)
    pdf.set_fill_color(252, 228, 236)
    pdf.set_font("Helvetica", "B", 9)
    pdf.multi_cell(0, 5, _latin1(DISCLAIMER), fill=True)
    return bytes(pdf.output())


def build_queue_pdf(rows: list[dict], model_version: str) -> bytes:
    """Récapitulatif de la file de priorité : rang, examen, niveau, risque estimé, relu."""
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(True, 18)
    pdf.add_page()
    pdf.set_fill_color(*ROSE)
    pdf.rect(0, 0, 210, 22, "F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 17)
    pdf.set_xy(12, 6)
    pdf.cell(0, 10, _latin1("EchoBreast - File de priorité"))
    pdf.set_text_color(40, 40, 40)
    pdf.set_xy(12, 28)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, _latin1(f"{dt.datetime.now():%d/%m/%Y %H:%M}   |   Version du modèle : {model_version}   |   "
                           f"{len(rows)} examen(s)"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    widths = [14, 84, 40, 32, 16]
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(244, 234, 245)
    for w, h in zip(widths, ["Rang", "Examen", "Niveau", "Risque estimé", "Relu"]):
        pdf.cell(w, 8, _latin1(h), border=0, fill=True)
    pdf.ln(8)
    pdf.set_font("Helvetica", "", 10)
    for i, r in enumerate(rows, 1):
        lv = LEVELS[r["level"]]
        col = tuple(int(lv["color"][k:k + 2], 16) for k in (1, 3, 5))
        pdf.cell(widths[0], 8, str(i))
        pdf.cell(widths[1], 8, _latin1(r["name"][:38]))
        pdf.set_text_color(*col)
        pdf.cell(widths[2], 8, _latin1(lv["label"]))
        pdf.set_text_color(40, 40, 40)
        pdf.cell(widths[3], 8, f"{r['p']:.0%}")
        pdf.cell(widths[4], 8, "oui" if r.get("relu") else "-", new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(239, 225, 234)
        pdf.line(12, pdf.get_y(), 198, pdf.get_y())
    pdf.ln(6)
    pdf.set_fill_color(252, 228, 236)
    pdf.set_font("Helvetica", "B", 9)
    pdf.multi_cell(0, 5, _latin1(DISCLAIMER), fill=True)
    return bytes(pdf.output())
