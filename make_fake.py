from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

txns = [
    ("2026-01-02", "OPENING BALANCE", 0.00),
    ("2026-01-03", "WOOLWORTHS 1234", -45.20),
    ("2026-01-05", "SALARY PAYMENT", 3200.00),
    ("2026-01-06", "TRANSPORT OPAL", -12.40),
    ("2026-01-09", "RENT PAYMENT", -850.00),
    ("2026-01-12", "COLES 5678", -63.15),
    ("2026-01-15", "REFUND AMAZON", 29.99),
    ("2026-01-18", "ELECTRICITY BILL", -140.55),
    ("2026-01-22", "CAFE PABLO", -8.50),
    ("2026-01-28", "GYM MEMBERSHIP", -49.00),
]

opening = 1000.00
bal = opening
rows = []
for d, desc, amt in txns:
    bal = round(bal + amt, 2)
    rows.append([d, desc, amt, bal])

def draw(path, rows):
    c = canvas.Canvas(path, pagesize=A4)
    c.setFont("Helvetica-Bold", 14); c.drawString(50, 800, "FAKE BANK  Statement of Account")
    c.setFont("Helvetica", 9); c.drawString(50, 785, "Account 000-111  Sample fixture (not real)")
    c.setFont("Helvetica-Bold", 9)
    c.drawString(50,760,"Date"); c.drawString(130,760,"Description"); c.drawString(370,760,"Amount"); c.drawString(470,760,"Balance")
    c.setFont("Helvetica", 9)
    y = 745
    for d, desc, amt, b in rows:
        c.drawString(50,y,d); c.drawString(130,y,desc)
        c.drawRightString(430,y,f"{amt:.2f}"); c.drawRightString(540,y,f"{b:.2f}")
        y -= 15
    c.save()

draw("fake_statement_ok.pdf", rows)

bad = [r[:] for r in rows]
bad[5][3] = round(bad[5][3] + 10.00, 2)   # corrupt row 5's balance by $10
draw("fake_statement_error.pdf", bad)

print("Wrote fake_statement_ok.pdf (all ties) and fake_statement_error.pdf (row 5 balance off by $10)")