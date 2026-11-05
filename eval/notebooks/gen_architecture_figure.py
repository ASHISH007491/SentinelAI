import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

fig, ax = plt.subplots(figsize=(9.7, 6.7), dpi=100)
ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis("off")

def box(cx, cy, w, h, text, fc, ec="#2c3e50"):
    ax.add_patch(FancyBboxPatch((cx-w/2, cy-h/2), w, h,
        boxstyle="round,pad=0.6,rounding_size=2.2", fc=fc, ec=ec, lw=1.6))
    ax.text(cx, cy, text, ha="center", va="center", fontsize=11, color="#1a1a1a")

def arrow(x1,y1,x2,y2, color="#5b6b8c", lw=2.0, style="-|>"):
    ax.add_patch(FancyArrowPatch((x1,y1),(x2,y2), arrowstyle=style,
        mutation_scale=16, color=color, lw=lw, shrinkA=2, shrinkB=2))

ax.text(50, 96, "SentinelAI architecture (simplified)", ha="center",
        fontsize=15, weight="bold")

BLUE="#dfe6fb"; LBLUE="#eaf1fd"; RED="#fbe0e0"; GREEN="#e2f3e2"
# vertical stack
box(50, 86, 46, 9, "Analyst  (human-in-the-loop)\nFastAPI + Next.js UI", BLUE)
box(50, 71, 46, 9, "Orchestrator\n(intent → plan → dispatch)", LBLUE)
box(50, 56, 46, 9, "PromptGuard  (injection guardrail)\nsanitises untrusted input", RED, ec="#c0392b")
# agents row
box(16, 39, 20, 9, "Prioritisation", LBLUE)
box(38.5, 39, 20, 9, "Indicator\nextraction", LBLUE)
box(61.5, 39, 20, 9, "Phishing\nverdict", LBLUE)
box(84, 39, 20, 9, "Code\nreview", LBLUE)
ax.text(50, 47.5, "Agents", ha="center", fontsize=9.5, color="#555", style="italic")
box(50, 22, 46, 9, "Reporting layer\n(findings + advisor)", GREEN, ec="#27ae60")

# main flow arrows
arrow(50, 81.5, 50, 75.5)          # analyst -> orchestrator
arrow(50, 66.5, 50, 60.5)          # orchestrator -> guard
# guard -> each agent
for x in (16, 38.5, 61.5, 84):
    arrow(50, 51.5, x, 43.5)
# each agent -> reporting
for x in (16, 38.5, 61.5, 84):
    arrow(x, 34.5, 50, 26.5)
# reporting -> analyst (results back), curved up the side
ret = FancyArrowPatch((73, 22), (73, 86), connectionstyle="arc3,rad=-0.28",
    arrowstyle="-|>", mutation_scale=16, color="#8a94a6", lw=1.8)
ax.add_patch(ret)
ax.text(88, 55, "results\nreturned to\nanalyst", ha="center", va="center",
        fontsize=8.5, color="#8a94a6")
# guard callout
ax.text(50, 56-6.6, "", ha="center")
ax.annotate("untrusted artefacts are sanitised\nhere, before any agent sees them",
    xy=(27, 56), xytext=(6, 63), fontsize=8.5, color="#c0392b", ha="left",
    arrowprops=dict(arrowstyle="->", color="#c0392b", lw=1.2))

plt.tight_layout()
plt.savefig("/tmp/fig_architecture.png", dpi=100, bbox_inches="tight",
            facecolor="white")
print("saved")
