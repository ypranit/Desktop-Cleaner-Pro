import csv
import io
import shutil
from datetime import datetime
from pathlib import Path

import plotly.express as px
import streamlit as st

# ----------------------------
# Page Config
# ----------------------------
st.set_page_config(
    page_title="Smart Desktop Cleaner Pro",
    page_icon="🧹",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ----------------------------
# Styling
# ----------------------------
st.markdown(
    """
    <style>
        .block-container {
            max-width: 1300px;
            padding-top: 1rem;
        }

        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #111827 0%, #0f172a 100%);
        }

        .hero {
            padding: 42px 28px;
            border-radius: 28px;
            background: linear-gradient(135deg, #2563eb 0%, #7c3aed 50%, #ec4899 100%);
            color: white;
            text-align: center;
            box-shadow: 0 18px 40px rgba(0, 0, 0, 0.28);
            margin-bottom: 24px;
        }

        .hero h1 {
            margin: 0;
            font-size: 56px;
            font-weight: 900;
            letter-spacing: -1.2px;
        }

        .hero p {
            margin-top: 12px;
            font-size: 20px;
            opacity: 0.95;
        }

        .section-title {
            font-size: 34px;
            font-weight: 850;
            margin: 14px 0 8px 0;
        }

        .subtle {
            color: #94a3b8;
            font-size: 0.98rem;
            margin-bottom: 8px;
        }

        .stButton > button {
            width: 100%;
            height: 64px;
            border-radius: 18px;
            font-size: 18px;
            font-weight: 800;
            border: none;
            background: linear-gradient(135deg, #2563eb, #7c3aed);
            color: white;
            box-shadow: 0 10px 25px rgba(37, 99, 235, 0.24);
        }

        .stButton > button:hover {
            transform: translateY(-1px);
            box-shadow: 0 12px 28px rgba(37, 99, 235, 0.32);
        }

        div[data-testid="stMetric"] {
            background: #0f172a;
            border: 1px solid #334155;
            border-radius: 18px;
            padding: 14px 16px;
            box-shadow: 0 8px 18px rgba(0,0,0,0.08);
        }

        div[data-testid="stMetric"] label {
            color: #cbd5e1 !important;
            font-weight: 700 !important;
        }

        div[data-testid="stMetric"] div {
            color: white !important;
            font-weight: 900 !important;
        }

        .card {
            background: #0f172a;
            border: 1px solid #334155;
            border-radius: 18px;
            padding: 16px;
            margin-bottom: 12px;
        }

        .pill {
            display: inline-block;
            padding: 6px 10px;
            border-radius: 999px;
            background: rgba(255,255,255,0.1);
            margin-right: 8px;
            margin-bottom: 8px;
            font-size: 0.9rem;
        }

        .good { color: #34d399; }
        .warn { color: #fbbf24; }
        .bad  { color: #fb7185; }

        .footer {
            text-align: center;
            color: #94a3b8;
            font-size: 0.92rem;
            margin: 18px 0 6px;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# ----------------------------
# File Type Rules
# ----------------------------
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg"}
DOC_EXTS = {".pdf", ".txt", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx"}
CODE_EXTS = {".py", ".js", ".ts", ".html", ".css", ".json", ".md", ".yaml", ".yml", ".ipynb"}
ARCHIVE_EXTS = {".zip", ".rar", ".7z", ".tar", ".gz"}
SHORTCUT_EXTS = {".lnk", ".url"}
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi"}


# ----------------------------
# Helpers
# ----------------------------
def detect_desktop_path() -> Path:

    if (Path.home() / "Desktop").exists():
        return Path.home() / "Desktop"

    if (Path.home() / "OneDrive" / "Desktop").exists():
        return Path.home() / "OneDrive" / "Desktop"

    # Streamlit Cloud fallback
    return Path.cwd()

def is_inside(child: Path, parent: Path) -> bool:
    try:
        child_resolved = child.resolve()
        parent_resolved = parent.resolve()
        return child_resolved == parent_resolved or parent_resolved in child_resolved.parents
    except Exception:
        return str(parent).lower() in str(child).lower()


def human_size(num_bytes: int) -> float:
    return round(num_bytes / (1024 * 1024), 2)


def categorize_file(item: Path) -> str:
    ext = item.suffix.lower()
    if ext in IMAGE_EXTS:
        return "Images"
    if ext in DOC_EXTS:
        return "Documents"
    if ext in CODE_EXTS:
        return "Code"
    if ext in ARCHIVE_EXTS:
        return "Archives"
    if ext in SHORTCUT_EXTS:
        return "Shortcuts"
    if ext in AUDIO_EXTS:
        return "Audio"
    if ext in VIDEO_EXTS:
        return "Video"
    return "Others"


def scan_desktop(scan_root: Path, output_root: Path, show_hidden: bool = False):
    """
    Returns:
        entries: list of dicts
        stats: dict
    """
    stats = {
        "total_items": 0,
        "files": 0,
        "folders": 0,
        "images": 0,
        "documents": 0,
        "code": 0,
        "archives": 0,
        "shortcuts": 0,
        "audio": 0,
        "video": 0,
        "others": 0,
        "large_files": 0,
    }

    entries = []

    if not scan_root.exists():
        return entries, stats

    for item in sorted(scan_root.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
        try:
            if not show_hidden and item.name.startswith("."):
                continue

            if is_inside(item, output_root):
                continue

            info = item.stat()

            if item.is_dir():
                stats["folders"] += 1
                category = "Folders"
                kind = "Folder"
                size_mb = 0.0
                modified = datetime.fromtimestamp(info.st_mtime).strftime("%Y-%m-%d %H:%M")
            else:
                stats["files"] += 1
                category = categorize_file(item)
                kind = "File"
                size_mb = human_size(info.st_size)
                modified = datetime.fromtimestamp(info.st_mtime).strftime("%Y-%m-%d %H:%M")

                if size_mb >= 50:
                    stats["large_files"] += 1

                key = category.lower()
                if key in stats:
                    stats[key] += 1
                else:
                    stats["others"] += 1

            stats["total_items"] += 1

            entries.append(
                {
                    "Name": item.name,
                    "Type": kind,
                    "Category": category,
                    "Size MB": size_mb,
                    "Modified": modified,
                    "Path": str(item),
                }
            )

        except Exception:
            continue

    return entries, stats


def organize_desktop(scan_root: Path, output_root: Path, show_hidden: bool = False, preview_only: bool = True):
    """
    Moves files into category folders under output_root.
    Returns logs and moved_count.
    """
    dest_map = {
        "Images": IMAGE_EXTS,
        "Documents": DOC_EXTS,
        "Code": CODE_EXTS,
        "Archives": ARCHIVE_EXTS,
        "Shortcuts": SHORTCUT_EXTS,
        "Audio": AUDIO_EXTS,
        "Video": VIDEO_EXTS,
        "Others": set(),
    }

    output_root.mkdir(parents=True, exist_ok=True)
    for folder in dest_map:
        (output_root / folder).mkdir(parents=True, exist_ok=True)

    logs = []
    moved_count = 0

    if not scan_root.exists():
        return logs, moved_count

    for item in sorted(scan_root.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
        try:
            if not show_hidden and item.name.startswith("."):
                continue

            if is_inside(item, output_root):
                continue

            if item.is_dir():
                logs.append(
                    {
                        "Item": item.name,
                        "Category": "Folder",
                        "Action": "Skipped folder",
                        "Destination": "—",
                        "Status": "Skipped",
                    }
                )
                continue

            category = categorize_file(item)
            destination_folder = output_root / category
            destination_folder.mkdir(parents=True, exist_ok=True)
            destination = destination_folder / item.name

            if preview_only:
                action = "Would move"
                status = "Preview"
            else:
                shutil.move(str(item), str(destination))
                moved_count += 1
                action = "Moved"
                status = "Done"

            logs.append(
                {
                    "Item": item.name,
                    "Category": category,
                    "Action": action,
                    "Destination": str(destination),
                    "Status": status,
                }
            )

        except Exception as e:
            logs.append(
                {
                    "Item": item.name,
                    "Category": "Error",
                    "Action": f"Failed: {e}",
                    "Destination": "—",
                    "Status": "Error",
                }
            )

    return logs, moved_count


def to_csv(rows, fieldnames):
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()

def get_suggestions(stats):
    suggestions = []

    if stats["shortcuts"] > 0:
        suggestions.append(
            f"Move {stats['shortcuts']} shortcuts into a Shortcuts folder."
        )

    if stats["images"] > 10:
        suggestions.append(
            "You have many images. Auto-archive them into Images."
        )

    if stats["documents"] > 10:
        suggestions.append(
            "Documents are piling up. Sort PDFs and docs into Documents."
        )

    if stats["code"] > 0:
        suggestions.append(
            "Code files detected. Keep them inside a Projects folder, not on the Desktop."
        )

    if stats["archives"] > 0:
        suggestions.append(
            "Archive files found. Move them into Archives."
        )

    if stats["large_files"] > 0:
        suggestions.append(
            "Large files detected. Review them before moving."
        )

    if stats["folders"] > 8:
        suggestions.append(
            "A lot of folders are on the Desktop. Consider moving older folders into Archive."
        )

    if not suggestions:
        suggestions.append(
            "Desktop looks pretty clean. Nice job."
        )

    return suggestions

def get_old_files(entries, days=90):
    old_files = []

    cutoff = datetime.now().timestamp() - (days * 24 * 60 * 60)

    for file in entries:
        try:
            modified_time = datetime.strptime(
                file["Modified"],
                "%Y-%m-%d %H:%M"
            ).timestamp()

            if modified_time < cutoff:
                old_files.append(file)

        except Exception:
            continue

    return old_files

def get_extension_counts(entries):
    counts = {}

    for file in entries:
        if file["Type"] != "File":
            continue

        extension = Path(file["Name"]).suffix.lower()

        if extension == "":
            extension = "No Extension"

        counts[extension] = counts.get(extension, 0) + 1

    return counts

def get_folder_sizes(scan_root):
    folders = []

    for item in scan_root.iterdir():

        if item.is_dir():

            total_size = 0

            try:
                for file in item.rglob("*"):

                    if file.is_file():

                        total_size += file.stat().st_size

            except:
                pass

            folders.append(
                {
                    "Folder": item.name,
                    "Size MB": round(total_size / (1024 * 1024), 2)
                }
            )

    folders.sort(
        key=lambda x: x["Size MB"],
        reverse=True
    )

    return folders

def get_desktop_health(stats, old_files_count):

    score = 100

    score -= stats["large_files"] * 10
    score -= old_files_count * 5
    score -= stats["folders"] * 2

    score = max(score,0)

    if score >= 80:
        status = "🟢 Healthy Desktop"
    elif score >= 50:
        status = "🟡 Moderate Clutter"
    else:
        status = "🔴 Needs Cleanup"
    return score, status  

def get_duplicates(entries):

    duplicates = {}

    for file in entries:

        name = file["Name"]

        if name not in duplicates:
            duplicates[name] = []

        duplicates[name].append(file)

    duplicates = {
        name: files
        for name, files in duplicates.items()
        if len(files) > 1
    }

    return duplicates


def get_recent_files(entries, days=7):

    recent_files = []

    cutoff = datetime.now().timestamp() - (
        days * 24 * 60 * 60
    )

    for file in entries:

        try:
            modified_time = datetime.strptime(
                file["Modified"],
                "%Y-%m-%d %H:%M"
            ).timestamp()

            if modified_time >= cutoff:
                recent_files.append(file)

        except:
            pass

    return recent_files

def get_largest_files(entries):
    files = [
        file for file in entries
        if file["Type"] == "File"
    ]

    files.sort(
        key=lambda x: x["Size MB"],
        reverse=True
    )

    return files[:5]
    
def glass_card(title, value):

    st.markdown(
        f"""
        <div style="
        background:rgba(15,23,42,0.7);
        border:1px solid rgba(255,255,255,0.1);
        border-radius:20px;
        padding:25px;
        text-align:center;
        box-shadow:0px 8px 25px rgba(0,0,0,.3);
        backdrop-filter: blur(15px);
        ">
            <h4>{title}</h4>
            <h1>{value}</h1>
        </div>
        """,
        unsafe_allow_html=True
    ) 

# ----------------------------
# Session State
# ----------------------------
if "scan_entries" not in st.session_state:
    st.session_state.scan_entries = []

if "scan_stats" not in st.session_state:
    st.session_state.scan_stats = None

if "cleanup_logs" not in st.session_state:
    st.session_state.cleanup_logs = []

if "moved_count" not in st.session_state:
    st.session_state.moved_count = 0

if "last_action" not in st.session_state:
    st.session_state.last_action = "Idle"


# ----------------------------
# Hero
# ----------------------------
st.markdown(
        """
        <div class="hero">
        <h1>🧹 Desktop Cleaner Pro</h1>

    <p>
    Safe Preview Architecture
    <br>
    Fast • Smart • Organized
    </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ----------------------------
# Sidebar
# ----------------------------
st.sidebar.title("🚀 Control Center")
st.sidebar.success("🟢 System Ready")

default_desktop = detect_desktop_path()
scan_root_str = st.sidebar.text_input("Folder to scan", value=str(default_desktop))
output_root_str = st.sidebar.text_input(
    "Organize into",
    value=str(Path(scan_root_str) / "Desktop_Organized"),
)

safe_mode = st.sidebar.toggle("Preview only (safe mode)", value=True)
show_hidden = st.sidebar.toggle("Show hidden files", value=False)
rows_to_show = st.sidebar.slider("Rows to display", min_value=5, max_value=50, value=15, step=5)
page = st.sidebar.radio(
    "Navigation",
    [
        "🏠 Dashboard",
        "📁 Files",
        "📊 Analytics",
        "📋 Reports"
    ]
)

st.sidebar.markdown("""
## 🚀 Smart Desktop Cleaner Pro

### ✅ Features

🔍 Scanner

👀 Safe Preview

📂 Auto Organization

📈 Analytics

🕒 Old Files

🔍 Search Files

📁 Folder Sizes

📄 CSV Reports

---

### 🏷 Version

v2.0
""")

# ----------------------------
# Path Validation
# ----------------------------
scan_root = Path(scan_root_str).expanduser()
output_root = Path(output_root_str).expanduser()

if output_root.resolve() == scan_root.resolve():
    output_root = scan_root / "Desktop_Organized"

if not scan_root.exists():
    st.error(f"Folder not found: {scan_root}")
    st.stop()

# ----------------------------
# Main Controls
# ----------------------------
st.markdown("# 1. Desktop Actions")
st.write("Scan first, preview the cleanup, then organize only when you are ready.")

c1, c2, c3 = st.columns(3)

with c1:
    scan_clicked = st.button("🔍 Scan Desktop", use_container_width=True)

with c2:
    preview_clicked = st.button("👀 Preview Cleanup", use_container_width=True)

with c3:
    organize_clicked = st.button("✨ Organize Desktop", use_container_width=True)

# ----------------------------
# Scan / Preview / Organize
# ----------------------------
if scan_clicked or preview_clicked or organize_clicked:
    with st.spinner("Reading desktop..."):
        entries, stats = scan_desktop(scan_root, output_root, show_hidden=show_hidden)
        st.session_state.scan_entries = entries
        st.session_state.scan_stats = stats
        st.session_state.last_action = "Scanned"

    if preview_clicked or organize_clicked:
        with st.spinner("Building cleanup plan..."):
            logs, moved = organize_desktop(
                scan_root,
                output_root,
                show_hidden=show_hidden,
                preview_only=(safe_mode or preview_clicked),
            )
            st.session_state.cleanup_logs = logs
            st.session_state.moved_count = moved
            st.session_state.last_action = "Previewed" if (safe_mode or preview_clicked) else "Organized"

        if organize_clicked and not safe_mode:
            st.success(f"Organized {moved} files successfully!")
        elif organize_clicked and safe_mode:
            st.warning("Safe mode is ON, so this was a preview only. Turn it off to move files.")

# ----------------------------
# Summary Cards
# ----------------------------
# ----------------------------
# Pages
# ----------------------------

if page == "🏠 Dashboard":

    stats = st.session_state.scan_stats

    if stats:

        st.subheader("📊 Desktop Analytics")

        r1, r2, r3, r4, r5 = st.columns(5)

        with r1:
            glass_card("Files", stats["files"])

        with r2:
            glass_card("Folders", stats["folders"])

        with r3:
            glass_card("Items", stats["total_items"])

        with r4:
            glass_card("Shortcuts", stats["shortcuts"])

        with r5:
            glass_card("Large Files", stats["large_files"])

        recent_files = get_recent_files(
            st.session_state.scan_entries
        )

        st.subheader("🕒 Recent Files")

        if recent_files:

            st.dataframe(
                recent_files,
                use_container_width=True
            )

        old_files = get_old_files(
            st.session_state.scan_entries
        )
        st.subheader("❤️ Desktop Health")

        health_score, health_status = get_desktop_health(
            stats,
            len(old_files)
        )

        st.progress(
            health_score/100
        )

        st.success(
            f"{health_status} ({health_score}%)"
        )

elif page == "📁 Files":

    st.subheader("📁 Files")

    if st.session_state.scan_entries:

        st.dataframe(
            st.session_state.scan_entries[:rows_to_show],
            use_container_width=True,
            hide_index=True
        )

        recent_files = get_recent_files(
            st.session_state.scan_entries
        )

        st.subheader("🕒 Recent Files")

        if recent_files:

            st.dataframe(
                recent_files,
                use_container_width=True,
                hide_index=True
            )

elif page == "📊 Analytics":

    st.subheader("📈 Analytics")

    if st.session_state.scan_entries:

        extension_counts = get_extension_counts(
            st.session_state.scan_entries
        )

        if extension_counts:

            chart_data = {
                "Extension": list(extension_counts.keys()),
                "Count": list(extension_counts.values())
            }

            fig = px.pie(
                chart_data,
                names="Extension",
                values="Count",
                hole=0.65,
                color_discrete_sequence=px.colors.sequential.Plasma
            )

            fig.update_layout(
                paper_bgcolor="#0f172a",
                plot_bgcolor="#0f172a",
                font_color="white",
                title="File Type Distribution"
            )

            st.plotly_chart(
                fig,
                use_container_width=True
            )

        else:

            st.info(
                "No files found to analyze."
            )

        folder_sizes = get_folder_sizes(
            scan_root
        )

        st.subheader("📁 Folder Sizes")

        fig = px.bar(
            folder_sizes,
            x="Folder",
            y="Size MB",
            color="Size MB"
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

elif page == "📋 Reports":

    st.subheader("📋 Cleanup Report")

    if st.session_state.cleanup_logs:

        st.dataframe(
            st.session_state.cleanup_logs,
            use_container_width=True,
            hide_index=True
        )


# ----------------------------
# Footer
# ----------------------------
st.markdown(
    f"""
    <div class="footer">
        Safe Preview Architecture | Python + Streamlit<br>
        Smart Desk Cleaner Pro | Version 2.0<br>
        {datetime.now().strftime('%Y-%m-%d %H:%M')}
    </div>
    """,
    unsafe_allow_html=True,
)