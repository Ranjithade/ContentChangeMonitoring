# 🇨🇦 Immigration Draw Monitor

A Python-based monitoring tool that tracks updates to Canadian federal and provincial immigration draw pages and sends Slack notifications when changes are detected.

This tool monitors Express Entry and multiple Provincial Nominee Program (PNP) websites and alerts you automatically when new draws or updates are published.

---

## 🚀 Features

- Monitors multiple official immigration websites
- Detects content changes using hash comparison
- Extracts structured draw information (date, invitations, CRS score)
- Uses Selenium for dynamic pages
- Sends formatted Slack notifications
- Logs activity and errors
- Saves previous content state locally

---

## 🌐 Websites Tracked

- IRCC Express Entry
- Ontario Immigrant Nominee Program (OINP)
- British Columbia PNP
- Manitoba Immigration
- Prince Edward Island
- Saskatchewan
- Alberta
- Quebec

(You can modify the URL list inside the script.)

---

## 🛠️ Tech Stack

- Python 3.9+
- requests
- BeautifulSoup4
- selenium
- undetected-chromedriver
- python-dateutil
- Slack Webhooks

---

## 📦 Installation

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/immigration-draw-monitor.git
cd immigration-draw-monitor
