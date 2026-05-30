#!/usr/bin/env python3
"""
elementor_builder.py — Elementor Pro JSON generator and WP REST API publisher.

Actions:
  --action build     : Generate Elementor JSON from content draft
  --action publish   : Publish page to WordPress via REST API
  --action update-llms : Add new page entry to llms.txt
"""

import argparse
import json
import os
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path

import requests


# ─────────────────────────────────────────────────────────────────
# UID generation
# ─────────────────────────────────────────────────────────────────

def uid():
    return uuid.uuid4().hex[:7]


# ─────────────────────────────────────────────────────────────────
# Widget builders
# ─────────────────────────────────────────────────────────────────

def widget(widget_type, settings):
    return {
        "id": uid(),
        "elType": "widget",
        "widgetType": widget_type,
        "settings": settings,
        "elements": [],
    }


def heading_widget(text, tag="h2", align="left", color=None):
    s = {"title": text, "header_size": tag, "align": align}
    if color:
        s["title_color"] = color
    return widget("heading", s)


def text_widget(html):
    return widget("text-editor", {"editor": html})


def button_widget(text, url="#contact", style="success", size="lg"):
    return widget("button", {
        "text": text,
        "link": {"url": url, "is_external": ""},
        "button_type": style,
        "size": size,
    })


def icon_list_widget(items):
    """items = list of {"text": str, "icon": {"value": "fas fa-check"}}"""
    return widget("icon-list", {
        "icon_list": [
            {"id": uid(), "text": item["text"],
             "selected_icon": {"value": item.get("icon", "fas fa-check"), "library": "fa-solid"}}
            for item in items
        ]
    })


def accordion_widget(faqs):
    """faqs = list of {"question": str, "answer": str}"""
    return widget("accordion", {
        "tabs": [
            {"id": uid(), "tab_title": faq["question"], "tab_content": faq["answer"]}
            for faq in faqs
        ]
    })


def star_rating_widget(rating=4.9, max_rating=5, label=""):
    return widget("star-rating", {
        "rating_scale": str(max_rating),
        "rating": str(rating),
        "star_style": "filled",
        "title": label,
        "align": "left",
    })


def counter_widget(number, suffix="", prefix="", label=""):
    return widget("counter", {
        "starting_number": 0,
        "ending_number": int(str(number).replace("+", "").replace(" ", "")),
        "prefix": prefix,
        "suffix": suffix,
        "title": label,
        "duration": 2000,
    })


def alert_widget(text, alert_type="warning", title=""):
    return widget("alert", {
        "alert_type": alert_type,
        "alert_title": title,
        "alert_description": text,
    })


def timeline_widget(steps):
    """steps = list of {"title": str, "description": str}"""
    return widget("timeline", {
        "list": [
            {"id": uid(), "item_title": s["title"], "item_description": s["description"]}
            for s in steps
        ]
    })


def price_list_widget(items):
    """items = list of {"name": str, "price": str, "description": str}"""
    return widget("price-list", {
        "price_list": [
            {
                "id": uid(),
                "title": item["name"],
                "price": item["price"],
                "item_description": item.get("description", ""),
            }
            for item in items
        ]
    })


def testimonial_widget(text, name, role="", rating=5):
    return widget("testimonial-carousel", {
        "slides": [
            {
                "id": uid(),
                "content": text,
                "name": name,
                "title": role,
                "rating": {"value": str(rating), "scale": "5"},
            }
        ]
    })


def breadcrumbs_widget(items):
    """items = list of {"label": str, "url": str}"""
    return widget("breadcrumbs", {
        "home_text": items[0]["label"] if items else "Accueil",
    })


def form_widget(fields=None):
    if fields is None:
        fields = ["Prénom", "Email", "Téléphone", "Message"]
    field_list = []
    for f in fields:
        ftype = "email" if f.lower() == "email" else "tel" if f.lower() in ("téléphone", "telephone") else "textarea" if f.lower() == "message" else "text"
        field_list.append({
            "id": uid(),
            "field_type": ftype,
            "field_label": f,
            "placeholder": f,
            "required": "yes" if f.lower() in ("email", "prénom") else "",
            "width": "100",
        })
    return widget("form", {
        "form_name": "Contact",
        "fields": field_list,
        "button_text": "Envoyer ma demande",
        "button_size": "md",
    })


def posts_widget(posts_per_page=3, category=""):
    return widget("posts", {
        "posts_per_page": posts_per_page,
        "columns": "3",
        "show_read_more": "yes",
        "read_more_text": "Lire la suite",
    })


# ─────────────────────────────────────────────────────────────────
# Column and Section builders
# ─────────────────────────────────────────────────────────────────

def column(widgets_list, size=100):
    return {
        "id": uid(),
        "elType": "column",
        "settings": {"_column_size": size},
        "elements": widgets_list,
    }


def section(columns_list, css_class="", bg_color=None, padding_v=60, full_width=False):
    s = {
        "custom_css_classes": css_class,
        "padding": {"unit": "px", "top": str(padding_v), "bottom": str(padding_v),
                    "left": "20", "right": "20", "isLinked": False},
    }
    if bg_color:
        s["background_background"] = "classic"
        s["background_color"] = bg_color
    if full_width:
        s["layout"] = "full_width"
        s["content_width"] = {"unit": "px", "size": 1200}
    return {
        "id": uid(),
        "elType": "section",
        "settings": s,
        "elements": columns_list,
    }


# ─────────────────────────────────────────────────────────────────
# Page template builder
# ─────────────────────────────────────────────────────────────────

def build_service_page(draft):
    """Build full Elementor JSON for a service page."""
    kw = draft["keyword"]
    name = draft["site_name"]
    city = draft.get("city", "")
    cta = draft.get("cta_text", "Prendre rendez-vous")
    intro = draft.get("intro_text", f"Découvrez {kw} avec {name}.")
    definition = draft.get("definition", f"{kw} est une approche thérapeutique qui permet de...")
    benefits = draft.get("benefits", [
        {"text": "Résultats rapides dès les premières séances"},
        {"text": "Méthode douce et non-médicamenteuse"},
        {"text": "Accompagnement personnalisé"},
    ])
    steps = draft.get("steps", [
        {"title": "Premier contact", "description": "Échange téléphonique gratuit pour définir votre besoin."},
        {"title": "Séance initiale", "description": "Anamnèse et premier protocole adapté à votre situation."},
        {"title": "Suivi", "description": "Séances de renforcement selon vos objectifs."},
    ])
    faqs = draft.get("faqs", [
        {"question": f"Comment fonctionne {kw} ?", "answer": f"{kw} agit en..."},
        {"question": f"Combien de séances sont nécessaires ?", "answer": "En moyenne 3 à 6 séances selon..."},
    ])
    prices = draft.get("prices", [
        {"name": "Séance individuelle", "price": "80€", "description": "Durée : 1h"},
    ])
    testimonials = draft.get("testimonials", [
        {"text": "Résultat impressionnant dès la 2ème séance.", "name": "Marie L.", "rating": 5},
    ])
    h1 = draft.get("h1", f"{kw.title()} {city} — {name}")
    bio = draft.get("bio", f"Praticien certifié avec plus de 10 ans d'expérience en {kw}.")

    sections = []

    # 1. HERO
    hero_widgets = [
        widget("animated-headline", {
            "headline_style": "highlighted",
            "before_text": kw.split()[0] if len(kw.split()) > 1 else kw,
            "highlighted_text": " ".join(kw.split()[1:]) if len(kw.split()) > 1 else "",
            "after_text": f"à {city}" if city else "",
            "header_size": "h1",
            "typography_typography": "custom",
            "typography_font_size": {"unit": "px", "size": 46},
            "title_color": "#FFFFFF",
        }),
        text_widget(f"<p style='color:#f0f0f0;font-size:18px;'>{intro}</p>"),
        button_widget(cta, "#contact", "success", "lg"),
        widget("star-rating", {
            "rating_scale": "5",
            "rating": "4.9",
            "title": "4.9/5 — Patients satisfaits",
            "align": "left",
            "marked_color": "#FFD700",
            "unmarked_color": "#AAAAAA",
        }),
        breadcrumbs_widget([{"label": "Accueil", "url": "/"}, {"label": kw, "url": ""}]),
    ]
    sections.append(section([column(hero_widgets)], "hero-section", "#1a1a2e", 100, True))

    # 2. DÉFINITION (AEO — réponse directe)
    sections.append(section([column([
        heading_widget(f"Qu'est-ce que {kw} ?", "h2"),
        text_widget(f"<p>{definition}</p>"),
        alert_widget(
            draft.get("alert_text", f"En bref : {kw} permet d'obtenir des résultats durables de façon naturelle."),
            "info",
            "À retenir",
        ),
    ])], "definition-section", "#F8F9FA"))

    # 3. BÉNÉFICES
    sections.append(section([column([
        heading_widget(f"Les {len(benefits)} bénéfices de {kw}", "h2"),
        icon_list_widget(benefits),
    ])], "benefits-section"))

    # 4. PROCESS / HowTo
    sections.append(section([column([
        heading_widget(f"Déroulement d'une séance de {kw}", "h2"),
        timeline_widget(steps),
    ])], "process-section", "#F8F9FA"))

    # 5. STATS / CREDIBILITÉ
    stats = draft.get("stats", [
        {"number": "10", "suffix": " ans", "label": "d'expérience"},
        {"number": "500", "suffix": "+", "label": "patients accompagnés"},
        {"number": "98", "suffix": "%", "label": "de satisfaction"},
    ])
    stat_widgets = [counter_widget(s["number"], s.get("suffix", ""), "", s["label"]) for s in stats]
    sections.append(section(
        [column([stat_widgets[i]], size=100 // len(stats)) for i in range(len(stats))],
        "stats-section", "#2C3E50"
    ))

    # 6. TARIFS
    sections.append(section([column([
        heading_widget(f"Tarifs {kw}{' à ' + city if city else ''}", "h2"),
        price_list_widget(prices),
        alert_widget(
            draft.get("price_note", "Remboursement partiel possible selon certaines mutuelles."),
            "warning",
            "Remboursement",
        ),
    ])], "pricing-section", "#F8F9FA"))

    # 7. TÉMOIGNAGES (E-E-A-T)
    testimonial_widgets = [
        testimonial_widget(t["text"], t["name"], t.get("role", ""), t.get("rating", 5))
        for t in testimonials
    ]
    sections.append(section([column([
        heading_widget("Avis de nos patients", "h2"),
        star_rating_widget(4.9, 5, "Note moyenne"),
        *testimonial_widgets,
    ])], "testimonials-section"))

    # 8. FAQ (FAQPage schema — AEO)
    sections.append(section([column([
        heading_widget(f"Questions fréquentes sur {kw}", "h2"),
        text_widget(f"<p>Vous avez des questions sur {kw} ? Retrouvez ci-dessous les réponses aux questions les plus fréquentes.</p>"),
        accordion_widget(faqs),
    ])], "faq-section", "#F8F9FA"))

    # 9. PRATICIEN / AUTORITÉ
    sections.append(section([column([
        heading_widget("Votre praticien", "h2"),
        text_widget(f"<p>{bio}</p>"),
        icon_list_widget(draft.get("certifications", [
            {"text": "Certifié par la Société Française d'Hypnose"},
            {"text": "Formation continue annuelle"},
        ])),
    ])], "authority-section"))

    # 10. MAILLAGE INTERNE
    sections.append(section([column([
        heading_widget("Découvrez aussi", "h2"),
        posts_widget(3),
    ])], "related-section", "#F8F9FA"))

    # 11. CTA FINAL + FORMULAIRE
    sections.append(section([column([
        heading_widget(draft.get("cta_title", f"Prêt à commencer votre séance de {kw} ?"), "h2", "center", "#FFFFFF"),
        text_widget(f"<p style='color:#f0f0f0;text-align:center;'>Contactez-nous dès aujourd'hui pour un premier échange gratuit.</p>"),
        form_widget(["Prénom", "Email", "Téléphone", "Message"]),
    ])], "contact-section", "#1a1a2e"))

    return {
        "version": "0.4",
        "title": draft.get("seo_title", h1),
        "type": "page",
        "content": sections,
    }


def build_page(draft):
    page_type = draft.get("page_type", "service")
    builders = {
        "service": build_service_page,
        "landing": build_service_page,
        "location": build_service_page,
    }
    builder = builders.get(page_type, build_service_page)
    return builder(draft)


# ─────────────────────────────────────────────────────────────────
# Schema JSON-LD generator
# ─────────────────────────────────────────────────────────────────

def build_schemas(draft):
    schemas = []
    kw = draft["keyword"]
    url = draft["page_url"]
    name = draft["site_name"]
    city = draft.get("city", "")
    profile_url = draft.get("profile_url", "")

    # Service schema
    schemas.append({
        "@context": "https://schema.org",
        "@type": "Service",
        "name": kw.title(),
        "description": draft.get("definition", f"{kw} à {city}"),
        "provider": {
            "@type": "LocalBusiness",
            "name": name,
            "url": profile_url,
        },
        "areaServed": {
            "@type": "City",
            "name": city,
        } if city else None,
        "url": url,
    })

    # FAQPage schema
    faqs = draft.get("faqs", [])
    if faqs:
        schemas.append({
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": faq["question"],
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": faq["answer"],
                    }
                }
                for faq in faqs
            ]
        })

    # BreadcrumbList schema
    schemas.append({
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Accueil", "item": profile_url},
            {"@type": "ListItem", "position": 2, "name": kw.title(), "item": url},
        ]
    })

    # HowTo schema (if steps present)
    steps = draft.get("steps", [])
    if steps and draft.get("page_type") in ("how_to", "service"):
        schemas.append({
            "@context": "https://schema.org",
            "@type": "HowTo",
            "name": f"Comment se déroule une séance de {kw}",
            "step": [
                {
                    "@type": "HowToStep",
                    "position": i + 1,
                    "name": s["title"],
                    "text": s["description"],
                }
                for i, s in enumerate(steps)
            ]
        })

    return [s for s in schemas if s is not None]


# ─────────────────────────────────────────────────────────────────
# WP REST API publisher
# ─────────────────────────────────────────────────────────────────

def detect_seo_plugin(wp_url, token):
    """Try to detect which SEO plugin is active."""
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(f"{wp_url}/wp-json", headers=headers, timeout=10)
        data = r.json()
        namespaces = data.get("namespaces", [])
        if "yoast/v1" in namespaces:
            return "yoast"
        if "rankmath/v1" in namespaces:
            return "rankmath"
        if "seopress/v1" in namespaces:
            return "seopress"
    except Exception:
        pass
    return "none"


def build_seo_meta(draft, seo_plugin):
    meta_title = draft.get("seo_title", draft["keyword"])
    meta_desc = draft.get("meta_description", "")
    focus_kw = draft.get("keyword", "")

    if seo_plugin == "yoast":
        return {
            "_yoast_wpseo_title": meta_title,
            "_yoast_wpseo_metadesc": meta_desc,
            "_yoast_wpseo_focuskw": focus_kw,
        }
    elif seo_plugin == "rankmath":
        return {
            "rank_math_title": meta_title,
            "rank_math_description": meta_desc,
            "rank_math_focus_keyword": focus_kw,
        }
    elif seo_plugin == "seopress":
        return {
            "_seopress_titles_title": meta_title,
            "_seopress_titles_desc": meta_desc,
        }
    return {}


def publish_page(profile, draft, elementor_json, schemas_json, status="draft"):
    wp_config = profile.get("credentials", {}).get("wp_rest", {})
    wp_url = wp_config.get("url", "").rstrip("/")
    token = wp_config.get("token", "")

    if not wp_url or not token:
        return {"error": "WP REST credentials not configured in profile", "status": None}

    seo_plugin = detect_seo_plugin(wp_url, token)

    # Inject schemas as custom HTML widget at end if no SEO plugin
    elementor_data = elementor_json.get("content", [])

    # Build schema injection section
    schema_html = "\n".join(
        f'<script type="application/ld+json">{json.dumps(s, ensure_ascii=False, indent=2)}</script>'
        for s in schemas_json
    )
    schema_section = section([column([
        widget("html", {"html": schema_html})
    ])], "schema-injection")

    if seo_plugin == "none":
        elementor_data.append(schema_section)

    elementor_json_str = json.dumps(elementor_data, ensure_ascii=False)

    # Build meta payload
    meta = {
        "_elementor_data": elementor_json_str,
        "_elementor_edit_mode": "builder",
        "_elementor_template_type": "wp-page",
        **build_seo_meta(draft, seo_plugin),
    }

    if seo_plugin != "none":
        # Inject schemas via Yoast/RankMath if available
        # Yoast allows custom schemas via _yoast_wpseo_schema_page_type
        pass

    payload = {
        "title": draft.get("h1", draft["keyword"]),
        "slug": draft["slug"],
        "status": status,
        "content": "",
        "meta": meta,
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    try:
        r = requests.post(
            f"{wp_url}/wp-json/wp/v2/pages",
            headers=headers,
            data=json.dumps(payload, ensure_ascii=False),
            timeout=30,
        )
        result = r.json()

        if r.status_code in (200, 201):
            post_id = result.get("id")
            link = result.get("link", "")
            preview = result.get("_links", {}).get("self", [{}])[0].get("href", "")
            return {
                "success": True,
                "wp_post_id": post_id,
                "status": status,
                "url": link,
                "preview_url": f"{wp_url}/?p={post_id}&preview=true",
                "seo_plugin": seo_plugin,
                "error": None,
            }
        else:
            return {
                "success": False,
                "error": result.get("message", f"HTTP {r.status_code}"),
                "code": result.get("code"),
                "status": None,
            }
    except requests.RequestException as e:
        return {"success": False, "error": str(e), "status": None}


# ─────────────────────────────────────────────────────────────────
# llms.txt updater
# ─────────────────────────────────────────────────────────────────

def update_llms_txt(profile_path, new_url, new_title, new_desc):
    profile = json.loads(Path(profile_path).read_text())
    site_url = profile.get("url", "").rstrip("/")
    domain = profile.get("domain", "")
    llms_path = Path(f"runs/{domain}/llms.txt")

    # Fetch current llms.txt if it exists locally
    if llms_path.exists():
        content = llms_path.read_text()
    else:
        content = f"# {profile.get('name', site_url)}\n> Site web de {profile.get('name', '')}.\n\n## Pages\n"

    entry = f"- [{new_title}]({new_url}): {new_desc}"

    # Find the right section or append
    if "## Services" in content and "service" in new_url.lower():
        content = content.replace("## Services\n", f"## Services\n{entry}\n", 1)
    elif "## Blog" in content and ("blog" in new_url.lower() or "article" in new_url.lower()):
        content = content.replace("## Blog", f"## Blog\n{entry}\n", 1)
    else:
        if "## Pages" not in content:
            content += "\n## Pages\n"
        content += f"{entry}\n"

    llms_path.parent.mkdir(parents=True, exist_ok=True)
    llms_path.write_text(content)

    return {"updated": True, "entry": entry, "llms_path": str(llms_path)}


# ─────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Elementor Pro JSON builder and WP publisher")
    parser.add_argument("--action", choices=["build", "publish", "update-llms"], default="build")
    parser.add_argument("--profile", required=True, help="Path to profiles/{domain}.json")
    parser.add_argument("--draft", help="Path to content draft JSON (for build action)")
    parser.add_argument("--elementor-json", help="Path to generated Elementor JSON (for publish)")
    parser.add_argument("--schema-json", help="Path to schemas JSON (for publish)")
    parser.add_argument("--output-dir", help="Output directory for generated files")
    parser.add_argument("--status", default="draft", choices=["draft", "private", "publish"])
    # For update-llms
    parser.add_argument("--new-page-url")
    parser.add_argument("--new-page-title")
    parser.add_argument("--new-page-desc")

    args = parser.parse_args()

    profile = json.loads(Path(args.profile).read_text())

    if args.action == "build":
        if not args.draft:
            print(json.dumps({"error": "--draft required for build action"}))
            sys.exit(1)

        draft = json.loads(Path(args.draft).read_text())
        draft["site_name"] = profile.get("name", "")
        draft["city"] = profile.get("geo", "").split(",")[0].strip()
        draft["profile_url"] = profile.get("url", "")

        elementor_json = build_page(draft)
        schemas_json = build_schemas(draft)

        slug = draft.get("slug", re.sub(r"[^a-z0-9]+", "-", draft["keyword"].lower()).strip("-"))
        output_dir = Path(args.output_dir or f"runs/{profile['domain']}/{datetime.now().strftime('%Y-%m-%d')}/content")
        output_dir.mkdir(parents=True, exist_ok=True)

        elementor_path = output_dir / f"{slug}-elementor.json"
        schemas_path = output_dir / f"{slug}-schemas.json"

        elementor_path.write_text(json.dumps(elementor_json, ensure_ascii=False, indent=2))
        schemas_path.write_text(json.dumps(schemas_json, ensure_ascii=False, indent=2))

        print(json.dumps({
            "success": True,
            "slug": slug,
            "sections_count": len(elementor_json["content"]),
            "schemas_count": len(schemas_json),
            "schemas": [s.get("@type") for s in schemas_json],
            "elementor_json_path": str(elementor_path),
            "schemas_json_path": str(schemas_path),
            "error": None,
        }, ensure_ascii=False))

    elif args.action == "publish":
        if not args.elementor_json or not args.schema_json:
            print(json.dumps({"error": "--elementor-json and --schema-json required for publish"}))
            sys.exit(1)

        # Re-read draft to get slug etc.
        slug = Path(args.elementor_json).stem.replace("-elementor", "")
        draft_path = Path(args.elementor_json).parent / f"{slug}-draft.json"

        if draft_path.exists():
            draft = json.loads(draft_path.read_text())
        else:
            # Infer minimal draft from elementor file name
            draft = {"keyword": slug.replace("-", " "), "slug": slug}

        draft["site_name"] = profile.get("name", "")
        draft["city"] = profile.get("geo", "").split(",")[0].strip()
        draft["profile_url"] = profile.get("url", "")

        elementor_json = json.loads(Path(args.elementor_json).read_text())
        schemas_json = json.loads(Path(args.schema_json).read_text())

        result = publish_page(profile, draft, elementor_json, schemas_json, args.status)

        # Log the publication
        log_dir = Path(args.elementor_json).parent
        log_path = log_dir / "publish-log.json"
        logs = []
        if log_path.exists():
            logs = json.loads(log_path.read_text())
        logs.append({
            "timestamp": datetime.now().isoformat(),
            "slug": slug,
            "status": args.status,
            "result": result,
        })
        log_path.write_text(json.dumps(logs, ensure_ascii=False, indent=2))

        print(json.dumps(result, ensure_ascii=False))

    elif args.action == "update-llms":
        result = update_llms_txt(
            args.profile,
            args.new_page_url,
            args.new_page_title,
            args.new_page_desc,
        )
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
