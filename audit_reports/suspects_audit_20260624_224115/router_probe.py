import json
from agent.router.xlam_router import XlamRouter

tests = [
    # Mission Control
    "activa mission control",
    "abre mision control",
    "activa tu mission control",
    "mostrar mission control",
    "open mission control",
    # Spaces
    "cambia al siguiente escritorio",
    "vuelve al escritorio anterior",
    "en qué escritorio estoy",
    # Windows
    "mueve la ventana activa a la derecha",
    "mueve la ventana activa a la izquierda",
    "move the active window to the left",
    "center the active window",
    # Browser / YouTube
    "ponme un video random en YouTube",
    "ponme un video random de tecnología en YouTube",
    "busca en YouTube un video de inteligencia artificial",
    "busca en internet noticias de inteligencia artificial",
    "abre https://chatgpt.com",
    # Canva
    "haz un post en Canva del día del padre",
    "hazme un post en Canva para Bellamar",
    "créame un diseño en Canva para una promoción de Bellamar",
    "diseñame un flyer en Canva",
    # Ambiguous
    "busca algo",
    "mueve la ventana",
]

router = XlamRouter()

rows = []
for text in tests:
    try:
        result = router.route(text)
        d = result.decision.model_dump()
        rows.append({
            "prompt": text,
            "intent": d.get("intent"),
            "domain": d.get("domain"),
            "action": d.get("action"),
            "route": d.get("route"),
            "needs_tool": d.get("needs_tool"),
            "needs_clarification": d.get("needs_clarification"),
            "missing_info": d.get("missing_info"),
            "suggested_plugins": d.get("suggested_plugins"),
            "suggested_skills": d.get("suggested_skills"),
            "suggested_tools": d.get("suggested_tools"),
            "model_used": getattr(result, "model_used", None),
            "corrected": getattr(result, "corrected", None),
            "raw": getattr(result, "raw", None),
            "error": getattr(result, "error", None),
        })
    except Exception as e:
        rows.append({"prompt": text, "error": repr(e)})

print(json.dumps(rows, indent=2, ensure_ascii=False))
