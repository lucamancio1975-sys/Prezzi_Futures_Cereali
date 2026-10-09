import os
import shutil
import re
import streamlit

def configure_pwa():
    """
    Configura Streamlit per abilitare l'installazione nativa come PWA su Chrome/Edge/Android/iOS:
    - Copia gli asset PWA (sw.js, manifest.json, icone e favicon) nella directory statica nativa di Streamlit.
    - Sostituisce la favicon predefinita di Streamlit con l'icona personalizzata del Grano.
    - Inietta i tag PWA (<link rel="manifest">, meta tag e registrazione di sw.js su scope '/') in index.html in modo idempotente e pulito.
    """
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        static_src = os.path.join(base_dir, "static")
        st_dir = os.path.dirname(streamlit.__file__)
        st_static = os.path.join(st_dir, "static")

        if not os.path.exists(st_static):
            return False

        # File da sincronizzare nella directory statica di Streamlit
        files_to_copy = [
            ("manifest.json", "manifest.json"),
            ("icon-180.png", "icon-180.png"),
            ("icon-192.png", "icon-192.png"),
            ("icon-512.png", "icon-512.png"),
            ("icon-maskable-512.png", "icon-maskable-512.png"),
            ("favicon.png", "favicon.png"),
            ("favicon.ico", "favicon.ico"),
            ("sw.js", "sw.js"),
        ]

        for src_name, dst_name in files_to_copy:
            src_path = os.path.join(static_src, src_name)
            dst_path = os.path.join(st_static, dst_name)
            if os.path.exists(src_path):
                shutil.copy2(src_path, dst_path)

        # Gestione di index.html
        index_path = os.path.join(st_static, "index.html")
        backup_path = os.path.join(st_static, "index.html.bak")
        
        # Se esiste il backup originale pulito, usa sempre quello come base per evitare accumulo di tag duplicati
        if os.path.exists(backup_path):
            with open(backup_path, "r", encoding="utf-8") as f:
                content = f.read()
        elif os.path.exists(index_path):
            with open(index_path, "r", encoding="utf-8") as f:
                content = f.read()
            # Salva backup per future invocazioni
            shutil.copy2(index_path, backup_path)
        else:
            return False

        # 1. Sostituzione titolo nativo 'Streamlit'
        content = re.sub(r'<title>.*?</title>', '<title>Futures Grano - Quotazioni Giornaliere</title>', content, flags=re.IGNORECASE)

        # 2. Sostituzione favicon nativa con percorsi puliti
        content = re.sub(r'<link\s+rel=["\']shortcut icon["\'].*?>', '', content, flags=re.IGNORECASE)

        pwa_marker = "<!-- PWA FUTURES GRANO V2 -->"
        pwa_tags = (
            f"    {pwa_marker}\n"
            f'    <link rel="shortcut icon" href="/app/static/favicon.png" />\n'
            f'    <link rel="icon" type="image/png" sizes="192x192" href="/app/static/icon-192.png" />\n'
            f'    <link rel="apple-touch-icon" sizes="180x180" href="/app/static/icon-180.png" />\n'
            f'    <link rel="manifest" href="/app/static/manifest.json" />\n'
            f'    <meta name="theme-color" content="#030712" />\n'
            f'    <meta name="application-name" content="Futures Grano" />\n'
            f'    <meta name="mobile-web-app-capable" content="yes" />\n'
            f'    <meta name="apple-mobile-web-app-capable" content="yes" />\n'
            f'    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />\n'
            f'    <meta name="apple-mobile-web-app-title" content="Futures Grano" />\n'
            f'    <script>\n'
            f'      // Protezione titolo e favicon da override React di Streamlit\n'
            f'      document.title = "Futures Grano - Quotazioni Giornaliere";\n'
            f'      if ("serviceWorker" in navigator) {{\n'
            f'        window.addEventListener("load", function() {{\n'
            f'          navigator.serviceWorker.register("/sw.js", {{ scope: "/" }})\n'
            f'            .then(function(reg) {{ console.log("PWA Service Worker registrato con successo:", reg.scope); }})\n'
            f'            .catch(function(err) {{ console.warn("Errore registrazione PWA Service Worker:", err); }});\n'
            f'        }});\n'
            f'      }}\n'
            f'    </script>\n'
        )

        content = content.replace("</head>", pwa_tags + "  </head>")

        with open(index_path, "w", encoding="utf-8") as f:
            f.write(content)

        return True
    except Exception as e:
        print(f"[PWA CONFIG WARNING] {e}")
        return False

if __name__ == "__main__":
    success = configure_pwa()
    print("PWA Configurazione completata:", success)
