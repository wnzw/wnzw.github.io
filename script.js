// Windows XP JavaScript Logic

// Global State
let activeWindow = null;
let zIndexCounter = 100;
let windowStates = {}; // Stores position and sizes of windows for restoring
let currentFolderId = null; // null means root of My Documents
let defaultCVText = "";

function getProjects() {
    let stored = localStorage.getItem('projects_data');
    if (stored) {
        try {
            return JSON.parse(stored);
        } catch(e) {
            console.error("Error parsing projects_data from localStorage", e);
        }
    }
    // Fallback to PROJECTS_DATA in projects-data.js (or custom_projects if legacy)
    const baseProjects = (typeof PROJECTS_DATA !== 'undefined' && Array.isArray(PROJECTS_DATA)) ? PROJECTS_DATA : [];
    let customProjects = [];
    try {
        customProjects = JSON.parse(localStorage.getItem('custom_projects')) || [];
    } catch (e) {}
    if (customProjects.length > 0) {
        const merged = [...baseProjects, ...customProjects];
        localStorage.setItem('projects_data', JSON.stringify(merged));
        localStorage.removeItem('custom_projects');
        return merged;
    }
    return baseProjects;
}

function resetLocalProjects() {
    if (confirm("هل أنت متأكد من رغبتك في حذف جميع التغييرات وإعادة المجلدات الافتراضية للموقع؟")) {
        localStorage.removeItem('projects_data');
        localStorage.removeItem('custom_projects');
        renderProjects();
    }
}

function loadSiteSettings() {
    let settings = {
        username: "Amjad",
        avatar: "👤",
        os_name: "Passion OS v2026",
        cpu: "ذهن بشري متكامل (Human Brain) @ 3.80GHz",
        ram: "16.0 جيجابايت من العزيمة والإصرار",
        wallpaper: "bliss_wallpaper.jpg"
    };
    
    // Load from global SITE_SETTINGS in projects-data.js if available
    if (typeof SITE_SETTINGS !== 'undefined' && SITE_SETTINGS) {
        settings = { ...settings, ...SITE_SETTINGS };
    }
    
    try {
        const stored = localStorage.getItem('site_settings');
        if (stored) {
            settings = { ...settings, ...JSON.parse(stored) };
        }
    } catch (e) {
        console.error("Error reading site settings from localStorage", e);
    }
    
    // Apply username and avatar
    const nameEl = document.getElementById('start-user-name');
    if (nameEl) nameEl.textContent = settings.username;
    const avatarEl = document.getElementById('start-user-avatar');
    if (avatarEl) avatarEl.textContent = settings.avatar;
    
    // Apply system info
    const osEl = document.getElementById('info-os-name');
    if (osEl) osEl.textContent = settings.os_name;
    const cpuEl = document.getElementById('info-cpu');
    if (cpuEl) cpuEl.textContent = settings.cpu;
    const ramEl = document.getElementById('info-ram');
    if (ramEl) ramEl.textContent = settings.ram;
    
    // Apply wallpaper
    const desktopEl = document.getElementById('desktop');
    if (desktopEl && settings.wallpaper) {
        if (settings.wallpaper.startsWith('http') || settings.wallpaper.includes('/') || settings.wallpaper.includes('.')) {
            desktopEl.style.backgroundImage = `url('${settings.wallpaper}')`;
        } else {
            desktopEl.style.backgroundImage = 'none';
            desktopEl.style.backgroundColor = settings.wallpaper;
        }
    }
    
    // Apply CV Text
    if (settings.cv_text) {
        defaultCVText = settings.cv_text;
        const notepadText = document.getElementById('notepad-text');
        if (notepadText) notepadText.value = settings.cv_text;
    }
    
    // Apply IE Links
    const ieLinksContainer = document.getElementById('ie-links-container');
    if (ieLinksContainer && settings.ie_links) {
        ieLinksContainer.innerHTML = '';
        settings.ie_links.forEach(link => {
            const a = document.createElement('a');
            a.href = link.url;
            a.target = '_blank';
            a.className = 'ie-card';
            a.innerHTML = `
                <span class="ie-card-icon">${link.icon || '🔗'}</span>
                <h3>${link.title}</h3>
                <p>${link.desc}</p>
            `;
            ieLinksContainer.appendChild(a);
        });
    
    // Apply Desktop apps configuration (Labels, Window titles, Page headers)
    let defaultApps = {
        computer: { label: "جهازي (My Computer)", title: "جهازي (My Computer)" },
        documents: { label: "مستنداتي (My Documents)", title: "مستنداتي (My Documents)" },
        ie: { label: "المتصفح (Internet Explorer)", title: "عن المطور - Internet Explorer", header: "بوابة التواصل والشبكات الاجتماعية", subheader: "أهلاً بك في صفحتي الشخصية عبر متصفح Internet Explorer الكلاسيكي!" },
        notepad: { label: "السيرة الذاتية (Notepad)", title: "السيرة_الذاتية.txt - مفكرة" },
        mediaplayer: { label: "Windows Media Player", title: "Windows Media Player" },
        minesweeper: { label: "كنس الألغام (Minesweeper)", title: "كنس الألغام (Minesweeper)" }
    };
    
    const apps = { ...defaultApps, ...(settings.desktop_apps || {}) };
    
    // Apply Desktop labels
    const lblComputer = document.getElementById('label-icon-computer');
    if (lblComputer) lblComputer.textContent = apps.computer.label;
    
    const lblDocuments = document.getElementById('label-icon-documents');
    if (lblDocuments) lblDocuments.textContent = apps.documents.label;
    
    const lblNotepad = document.getElementById('label-icon-notepad');
    if (lblNotepad) lblNotepad.textContent = apps.notepad.label;
    
    const lblIe = document.getElementById('label-icon-ie');
    if (lblIe) lblIe.textContent = apps.ie.label;
    
    const lblMinesweeper = document.getElementById('label-icon-minesweeper');
    if (lblMinesweeper) lblMinesweeper.textContent = apps.minesweeper.label;
    
    // Apply Window titles
    const winComputer = document.getElementById('title-text-computer');
    if (winComputer) winComputer.textContent = apps.computer.title;
    
    const winDocuments = document.getElementById('title-text-documents');
    if (winDocuments) winDocuments.textContent = apps.documents.title;
    
    const winNotepad = document.getElementById('title-text-notepad');
    if (winNotepad) winNotepad.textContent = apps.notepad.title;
    
    const winIe = document.getElementById('title-text-ie');
    if (winIe) winIe.textContent = apps.ie.title;
    
    const winMinesweeper = document.getElementById('title-text-minesweeper');
    if (winMinesweeper) winMinesweeper.textContent = apps.minesweeper.title;
    
    const winMediaPlayer = document.getElementById('title-text-mediaplayer');
    if (winMediaPlayer) winMediaPlayer.textContent = apps.mediaplayer.title;
    
    // Apply IE Page headers
    const ieHeader = document.getElementById('ie-page-header');
    if (ieHeader) ieHeader.textContent = apps.ie.header;
    
    const ieSubheader = document.getElementById('ie-page-subheader');
    if (ieSubheader) ieSubheader.textContent = apps.ie.subheader;
}

function openDefaultNotepad() {
    const notepadText = document.getElementById('notepad-text');
    const notepadWin = document.getElementById('win-notepad');
    if (!notepadText || !notepadWin) return;
    
    const titleEl = notepadWin.querySelector('.title-bar-text');
    titleEl.innerHTML = `<img class="window-mini-icon" src="data:image/svg+xml;utf8,<svg viewBox='0 0 48 48' xmlns='http://www.w3.org/2000/svg'><rect x='8' y='4' width='32' height='40' rx='3' fill='%23ECEFF1' stroke='%2337474F' stroke-width='2'/></svg>" alt=""> السيرة_الذاتية.txt - مفكرة`;
    notepadText.value = defaultCVText;
    
    openWindow('win-notepad');
}

function openNotepadWithFile(name, content) {
    const notepadText = document.getElementById('notepad-text');
    const notepadWin = document.getElementById('win-notepad');
    if (!notepadText || !notepadWin) return;
    
    const titleEl = notepadWin.querySelector('.title-bar-text');
    titleEl.innerHTML = `<img class="window-mini-icon" src="data:image/svg+xml;utf8,<svg viewBox='0 0 48 48' xmlns='http://www.w3.org/2000/svg'><rect x='8' y='4' width='32' height='40' rx='3' fill='%23ECEFF1' stroke='%2337474F' stroke-width='2'/></svg>" alt=""> ${name} - مفكرة`;
    notepadText.value = content;
    
    openWindow('win-notepad');
}

function openDownloadFile(name, urlOrContent) {
    if (urlOrContent.startsWith('http://') || urlOrContent.startsWith('https://')) {
        const link = document.createElement("a");
        link.href = urlOrContent;
        link.download = name;
        link.target = "_blank";
        link.click();
    } else {
        const blob = new Blob([urlOrContent], { type: "application/octet-stream" });
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = name;
        link.click();
    }
}

function openImageViewer(name, url) {
    const imgEl = document.getElementById('imageviewer-img');
    const win = document.getElementById('win-imageviewer');
    const status = document.getElementById('imageviewer-status');
    if (!imgEl || !win) return;
    
    imgEl.src = url;
    if (status) status.textContent = `معاينة: ${name}`;
    
    const titleEl = win.querySelector('.title-bar-text');
    if (titleEl) {
        titleEl.innerHTML = `<img class="window-mini-icon" src="data:image/svg+xml;utf8,<svg viewBox='0 0 48 48' xmlns='http://www.w3.org/2000/svg'><rect x='4' y='8' width='40' height='32' rx='3' fill='%234CAF50'/><circle cx='16' cy='18' r='4' fill='%23FFEB3B'/><path d='M4,32 L16,20 L28,32 Z' fill='%23388E3C'/></svg>" alt=""> ${name} - عارض الصور والفاكس`;
    }
    
    openWindow('win-imageviewer');
}

function openMediaPlayer(name, url) {
    const audioEl = document.getElementById('wmp-audio');
    const win = document.getElementById('win-mediaplayer');
    const filenameEl = document.getElementById('wmp-filename');
    const status = document.getElementById('wmp-status');
    if (!audioEl || !win) return;
    
    audioEl.src = url;
    audioEl.play().catch(err => console.log("Auto-play blocked or audio source error", err));
    if (filenameEl) filenameEl.textContent = name;
    if (status) status.textContent = 'تشغيل...';
    
    audioEl.onplay = () => { if (status) status.textContent = 'تشغيل...'; };
    audioEl.onpause = () => { if (status) status.textContent = 'متوقف مؤقتاً'; };
    audioEl.onended = () => { if (status) status.textContent = 'انتهى التشغيل'; };
    
    openWindow('win-mediaplayer');
}

function openIEWithURL(name, url) {
    const win = document.getElementById('win-ie');
    if (!win) return;
    
    const input = win.querySelector('.ie-address-input');
    if (input) input.value = url;
    
    openWindow('win-ie');
    
    // Open in new tab since most sites block being loaded in an iframe due to CORS
    window.open(url, '_blank');
}

// DOM Elements
const desktop = document.getElementById('desktop');
const startBtn = document.getElementById('start-btn');
const startMenu = document.getElementById('start-menu');
const trayClock = document.getElementById('tray-clock');
const taskbarTasks = document.getElementById('taskbar-tasks');

// 1. Z-Index and Focus Management
function focusWindow(windowEl) {
    if (!windowEl) return;
    
    // Deactivate current active window styling
    const currentActive = document.querySelector('.window.active-window');
    if (currentActive) {
        currentActive.classList.remove('active-window');
    }
    
    // Bring to front
    zIndexCounter += 1;
    windowEl.style.zIndex = zIndexCounter;
    windowEl.classList.add('active-window');
    activeWindow = windowEl;
    
    // Update taskbar button active class
    updateTaskbarActiveTab(windowEl.id);
}

// 2. Open / Close / Minimize / Maximize Window Controls
function openWindow(id) {
    const win = document.getElementById(id);
    if (!win) return;
    
    // Show window if hidden
    win.style.display = 'flex';
    
    // Focus window
    focusWindow(win);
    
    // Ensure taskbar tab is present
    createTaskbarTab(id, getWindowTitle(win));
    
    // Close start menu
    startMenu.style.display = 'none';
}

function getWindowTitle(win) {
    const titleTextEl = win.querySelector('.title-bar-text');
    // Get text content excluding child elements (like mini-icon image/svg)
    let title = '';
    titleTextEl.childNodes.forEach(node => {
        if (node.nodeType === Node.TEXT_NODE) {
            title += node.textContent;
        }
    });
    return title.trim() || 'نافذة';
}

function closeWindow(win) {
    win.style.display = 'none';
    removeTaskbarTab(win.id);
    
    // Stop WMP audio if closed
    if (win.id === 'win-mediaplayer') {
        const audio = document.getElementById('wmp-audio');
        if (audio) {
            audio.pause();
            audio.src = '';
        }
        const status = document.getElementById('wmp-status');
        if (status) status.textContent = 'متوقف';
    }
}

function minimizeWindow(win) {
    win.style.display = 'none';
    const tab = document.querySelector(`.task-button[data-window-id="${win.id}"]`);
    if (tab) {
        tab.classList.remove('active');
    }
}

function toggleMaximizeWindow(win) {
    const isMaximized = win.classList.contains('maximized');
    
    if (!isMaximized) {
        // Save restore dimensions
        windowStates[win.id] = {
            top: win.style.top,
            left: win.style.left,
            width: win.style.width,
            height: win.style.height
        };
        
        // Maximize
        win.classList.add('maximized');
        win.style.top = '0';
        win.style.left = '0';
        win.style.width = '100%';
        win.style.height = 'calc(100% - 30px)';
    } else {
        // Restore
        win.classList.remove('maximized');
        const state = windowStates[win.id];
        if (state) {
            win.style.top = state.top;
            win.style.left = state.left;
            win.style.width = state.width;
            win.style.height = state.height;
        }
    }
}

// 3. Taskbar Management
function createTaskbarTab(winId, title) {
    // Check if tab already exists
    let tab = document.querySelector(`.task-button[data-window-id="${winId}"]`);
    if (tab) return;
    
    tab = document.createElement('button');
    tab.className = 'task-button';
    tab.setAttribute('data-window-id', winId);
    
    // Get icon representation
    let icon = '📂';
    if (winId === 'win-computer') icon = '💻';
    if (winId === 'win-notepad') icon = '📝';
    if (winId === 'win-ie') icon = '🌐';
    if (winId === 'win-minesweeper') icon = '💣';
    if (winId === 'win-imageviewer') icon = '🖼️';
    if (winId === 'win-mediaplayer') icon = '🎵';
    
    tab.innerHTML = `<span class="task-icon">${icon}</span> ${title}`;
    
    // Clicking task button toggles minimize / restore / focus
    tab.addEventListener('click', () => {
        const win = document.getElementById(winId);
        if (!win) return;
        
        if (win.style.display === 'none') {
            win.style.display = 'flex';
            focusWindow(win);
        } else if (win.classList.contains('active-window')) {
            minimizeWindow(win);
        } else {
            focusWindow(win);
        }
    });
    
    taskbarTasks.appendChild(tab);
    updateTaskbarActiveTab(winId);
}

function removeTaskbarTab(winId) {
    const tab = document.querySelector(`.task-button[data-window-id="${winId}"]`);
    if (tab) {
        tab.remove();
    }
}

function updateTaskbarActiveTab(activeWinId) {
    document.querySelectorAll('.task-button').forEach(tab => {
        if (tab.getAttribute('data-window-id') === activeWinId) {
            tab.classList.add('active');
        } else {
            tab.classList.remove('active');
        }
    });
}

// 4. Draggable Windows Logic (Mouse & Touch)
function makeWindowDraggable(win) {
    const titleBar = win.querySelector('.title-bar');
    let posX = 0, posY = 0, mouseX = 0, mouseY = 0;
    
    titleBar.addEventListener('mousedown', dragMouseDown);
    titleBar.addEventListener('touchstart', dragTouchStart, { passive: false });
    
    function dragMouseDown(e) {
        if (win.classList.contains('maximized')) return;
        e.preventDefault();
        focusWindow(win);
        mouseX = e.clientX;
        mouseY = e.clientY;
        document.addEventListener('mouseup', closeDragElement);
        document.addEventListener('mousemove', elementDrag);
    }
    
    function dragTouchStart(e) {
        if (win.classList.contains('maximized')) return;
        focusWindow(win);
        const touch = e.touches[0];
        mouseX = touch.clientX;
        mouseY = touch.clientY;
        document.addEventListener('touchend', closeDragElement);
        document.addEventListener('touchmove', elementTouchDrag, { passive: false });
    }
    
    function elementDrag(e) {
        e.preventDefault();
        posX = mouseX - e.clientX;
        posY = mouseY - e.clientY;
        mouseX = e.clientX;
        mouseY = e.clientY;
        
        const top = win.offsetTop - posY;
        const left = win.offsetLeft - posX;
        
        // Prevent window from going offscreen completely
        win.style.top = `${Math.max(0, top)}px`;
        win.style.left = `${left}px`;
    }
    
    function elementTouchDrag(e) {
        // Prevent scroll
        e.preventDefault();
        const touch = e.touches[0];
        posX = mouseX - touch.clientX;
        posY = mouseY - touch.clientY;
        mouseX = touch.clientX;
        mouseY = touch.clientY;
        
        const top = win.offsetTop - posY;
        const left = win.offsetLeft - posX;
        
        win.style.top = `${Math.max(0, top)}px`;
        win.style.left = `${left}px`;
    }
    
    function closeDragElement() {
        document.removeEventListener('mouseup', closeDragElement);
        document.removeEventListener('mousemove', elementDrag);
        document.removeEventListener('touchend', closeDragElement);
        document.removeEventListener('touchmove', elementTouchDrag);
    }
}

// 5. Clock Tick in System Tray
function updateClock() {
    const now = new Date();
    let hours = now.getHours();
    const minutes = now.getMinutes();
    const ampm = hours >= 12 ? 'م' : 'ص';
    hours = hours % 12;
    hours = hours ? hours : 12; // 0 should be 12
    const strMinutes = minutes < 10 ? '0' + minutes : minutes;
    trayClock.textContent = `${hours}:${strMinutes} ${ampm}`;
}

// 6. Project Viewer (My Documents)
function openProject(id) {
    const allProjects = getProjects();
    const project = allProjects.find(p => p.id === id);
    if (!project) return;
    
    const panel = document.getElementById('project-detail-panel');
    const title = document.getElementById('proj-title');
    const desc = document.getElementById('proj-desc');
    const badge = document.getElementById('proj-badge');
    
    title.textContent = project.title;
    desc.textContent = project.description;
    badge.textContent = `التقنيات: ${project.technologies}`;
    
    panel.style.display = 'block';
}

function getFileDetails(filename, content) {
    const ext = filename.split('.').pop().toLowerCase();
    
    if (['jpg', 'jpeg', 'png', 'gif', 'webp'].includes(ext)) {
        return { icon: '🖼️', action: openImageViewer };
    } else if (['mp3', 'wav', 'ogg'].includes(ext)) {
        return { icon: '🎵', action: openMediaPlayer };
    } else if (['zip', 'rar', 'pdf', 'docx', 'xlsx', 'pptx', 'exe', 'dmg', 'tar', 'gz'].includes(ext)) {
        return { icon: '📥', action: openDownloadFile };
    } else if (['lnk', 'html', 'url'].includes(ext) || (content && (content.startsWith('http://') || content.startsWith('https://')))) {
        return { icon: '🔗', action: openIEWithURL };
    } else {
        return { icon: '📄', action: openNotepadWithFile };
    }
}

function renderProjects() {
    const grid = document.getElementById('projects-grid');
    const statusLeft = document.getElementById('documents-status-left');
    const btnDocUp = document.getElementById('btn-doc-up');
    const docCurrentPath = document.getElementById('doc-current-path');
    
    if (!grid) return;
    
    grid.innerHTML = '';
    
    const allProjects = getProjects();
    
    if (currentFolderId === null) {
        // We are at root level (display project folders)
        if (btnDocUp) btnDocUp.disabled = true;
        if (docCurrentPath) docCurrentPath.textContent = 'مستنداتي';
        
        allProjects.forEach(proj => {
            const item = document.createElement('div');
            item.className = 'file-item';
            item.tabIndex = 0;
            
            // Double click to enter project folder
            item.addEventListener('dblclick', () => {
                currentFolderId = proj.id;
                renderProjects();
            });
            
            // Touch support (double tap) to enter folder
            let lastTap = 0;
            item.addEventListener('touchend', (e) => {
                const currentTime = new Date().getTime();
                const tapLength = currentTime - lastTap;
                if (tapLength < 300 && tapLength > 0) {
                    currentFolderId = proj.id;
                    renderProjects();
                    e.preventDefault();
                } else {
                    // Single tap - show details
                    openProject(proj.id);
                }
                lastTap = currentTime;
            });
            
            // Single click to show details
            item.addEventListener('click', () => {
                item.focus();
                openProject(proj.id);
            });
            
            item.innerHTML = `
                <div class="file-icon">${proj.icon || '📁'}</div>
                <span class="file-label">${proj.title}</span>
            `;
            
            grid.appendChild(item);
        });
        
        if (statusLeft) {
            statusLeft.textContent = `عدد العناصر: ${allProjects.length} مجلدات`;
        }
    } else {
        // We are inside a project folder (display sub-files)
        const project = allProjects.find(p => p.id === currentFolderId);
        if (!project) return;
        
        if (btnDocUp) btnDocUp.disabled = false;
        if (docCurrentPath) docCurrentPath.textContent = `مستنداتي \\ ${project.title}`;
        
        // Hide details panel to keep clean layout
        const panel = document.getElementById('project-detail-panel');
        if (panel) panel.style.display = 'none';
        
        if (project.files && project.files.length > 0) {
            project.files.forEach(file => {
                const item = document.createElement('div');
                item.className = 'file-item';
                item.tabIndex = 0;
                
                const details = getFileDetails(file.name, file.content);
                
                // Double click to open text file in Notepad
                item.addEventListener('dblclick', () => {
                    details.action(file.name, file.content);
                });
                
                // Touch support (double tap) to open file
                let lastTap = 0;
                item.addEventListener('touchend', (e) => {
                    const currentTime = new Date().getTime();
                    const tapLength = currentTime - lastTap;
                    if (tapLength < 300 && tapLength > 0) {
                        details.action(file.name, file.content);
                        e.preventDefault();
                    }
                    lastTap = currentTime;
                });
                
                item.addEventListener('click', () => {
                    item.focus();
                });
                
                item.innerHTML = `
                    <div class="file-icon">${details.icon}</div>
                    <span class="file-label">${file.name}</span>
                `;
                
                grid.appendChild(item);
            });
            
            if (statusLeft) {
                statusLeft.textContent = `عدد العناصر: ${project.files.length} ملفات`;
            }
        } else {
            // Folder is empty
            const emptyMsg = document.createElement('div');
            emptyMsg.style.gridColumn = '1 / -1';
            emptyMsg.style.padding = '20px';
            emptyMsg.style.color = '#777';
            emptyMsg.style.fontStyle = 'italic';
            emptyMsg.style.textAlign = 'center';
            emptyMsg.textContent = 'هذا المجلد فارغ.';
            grid.appendChild(emptyMsg);
            
            if (statusLeft) {
                statusLeft.textContent = 'عدد العناصر: 0 ملفات';
            }
        }
    }
}

// 7. Notepad File Handling
function saveNotepadText() {
    const text = document.getElementById('notepad-text').value;
    const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    
    // Dynamically retrieve loaded file name from title bar
    const titleEl = document.getElementById('win-notepad').querySelector('.title-bar-text');
    let titleText = titleEl ? titleEl.textContent.trim() : "السيرة_الذاتية.txt";
    titleText = titleText.replace(" - مفكرة", "");
    
    link.download = titleText || "السيرة_الذاتية.txt";
    link.click();
}

function clearNotepad() {
    document.getElementById('notepad-text').value = '';
}

// 8. Minesweeper Game Engine
let msGrid = [];
let msRows = 9;
let msCols = 9;
let msMines = 10;
let msTimerId = null;
let msTime = 0;
let msMinesLeft = 10;
let msGameOver = false;
let msFirstClick = true;

const msGridEl = document.getElementById('minesweeper-grid');
const msMineCountEl = document.getElementById('ms-mine-count');
const msTimerEl = document.getElementById('ms-timer');
const msSmileyBtn = document.getElementById('ms-smiley-btn');

function initMinesweeper(rows = 9, cols = 9, mines = 10) {
    msRows = rows;
    msCols = cols;
    msMines = mines;
    msMinesLeft = mines;
    msTime = 0;
    msGameOver = false;
    msFirstClick = true;
    
    if (msTimerId) {
        clearInterval(msTimerId);
        msTimerId = null;
    }
    
    msTimerEl.textContent = '000';
    msMineCountEl.textContent = String(msMinesLeft).padStart(3, '0');
    msSmileyBtn.textContent = '😀';
    
    // Set grid css
    msGridEl.style.gridTemplateColumns = `repeat(${cols}, 20px)`;
    msGridEl.style.gridTemplateRows = `repeat(${rows}, 20px)`;
    
    // Reset Grid Array
    msGrid = Array(rows).fill(null).map(() => Array(cols).fill(null).map(() => ({
        mine: false,
        revealed: false,
        flagged: false,
        count: 0
    })));
    
    renderMinesweeperBoard();
}

function renderMinesweeperBoard() {
    msGridEl.innerHTML = '';
    
    for (let r = 0; r < msRows; r++) {
        for (let c = 0; c < msCols; c++) {
            const cellEl = document.createElement('div');
            cellEl.className = 'minesweeper-cell';
            cellEl.dataset.row = r;
            cellEl.dataset.col = c;
            
            // Mouse event handlers
            cellEl.addEventListener('click', () => handleCellClick(r, c));
            cellEl.addEventListener('contextmenu', (e) => {
                e.preventDefault();
                handleCellRightClick(r, c);
            });
            
            // Visual feedback when holding click down (smiley changes face)
            cellEl.addEventListener('mousedown', (e) => {
                if (e.button === 0 && !msGameOver) {
                    msSmileyBtn.textContent = '😮';
                }
            });
            cellEl.addEventListener('mouseup', () => {
                if (!msGameOver) {
                    msSmileyBtn.textContent = '😀';
                }
            });
            
            msGridEl.appendChild(cellEl);
        }
    }
}

function placeMines(firstRow, firstCol) {
    let minesPlaced = 0;
    while (minesPlaced < msMines) {
        const r = Math.floor(Math.random() * msRows);
        const c = Math.floor(Math.random() * msCols);
        
        // Prevent mine placing on the first clicked cell or its immediate neighbors
        const isSafeZone = Math.abs(r - firstRow) <= 1 && Math.abs(c - firstCol) <= 1;
        
        if (!msGrid[r][c].mine && !isSafeZone) {
            msGrid[r][c].mine = true;
            minesPlaced++;
        }
    }
    
    // Calculate counts
    for (let r = 0; r < msRows; r++) {
        for (let c = 0; c < msCols; c++) {
            if (msGrid[r][c].mine) continue;
            let count = 0;
            for (let dr = -1; dr <= 1; dr++) {
                for (let dc = -1; dc <= 1; dc++) {
                    const nr = r + dr;
                    const nc = c + dc;
                    if (nr >= 0 && nr < msRows && nc >= 0 && nc < msCols) {
                        if (msGrid[nr][nc].mine) count++;
                    }
                }
            }
            msGrid[r][c].count = count;
        }
    }
}

function startMinesweeperTimer() {
    msTimerId = setInterval(() => {
        msTime++;
        if (msTime > 999) {
            clearInterval(msTimerId);
        } else {
            msTimerEl.textContent = String(msTime).padStart(3, '0');
        }
    }, 1000);
}

function handleCellClick(r, c) {
    if (msGameOver) return;
    
    const cell = msGrid[r][c];
    if (cell.revealed || cell.flagged) return;
    
    if (msFirstClick) {
        msFirstClick = false;
        placeMines(r, c);
        startMinesweeperTimer();
    }
    
    if (cell.mine) {
        triggerMinesweeperLoss();
        return;
    }
    
    revealCell(r, c);
    checkMinesweeperWin();
}

function revealCell(r, c) {
    const cell = msGrid[r][c];
    if (cell.revealed) return;
    
    cell.revealed = true;
    const cellEl = msGridEl.children[r * msCols + c];
    cellEl.classList.add('revealed');
    
    if (cell.count > 0) {
        cellEl.textContent = cell.count;
        cellEl.dataset.num = cell.count;
    } else {
        // Flood fill reveal
        for (let dr = -1; dr <= 1; dr++) {
            for (let dc = -1; dc <= 1; dc++) {
                const nr = r + dr;
                const nc = c + dc;
                if (nr >= 0 && nr < msRows && nc >= 0 && nc < msCols) {
                    revealCell(nr, nc);
                }
            }
        }
    }
}

function handleCellRightClick(r, c) {
    if (msGameOver) return;
    const cell = msGrid[r][c];
    if (cell.revealed) return;
    
    const cellEl = msGridEl.children[r * msCols + c];
    
    if (!cell.flagged) {
        cell.flagged = true;
        cellEl.classList.add('flagged');
        cellEl.textContent = '🚩';
        msMinesLeft--;
    } else {
        cell.flagged = false;
        cellEl.classList.remove('flagged');
        cellEl.textContent = '';
        msMinesLeft++;
    }
    
    msMineCountEl.textContent = String(Math.max(0, msMinesLeft)).padStart(3, '0');
}

function triggerMinesweeperLoss() {
    msGameOver = true;
    clearInterval(msTimerId);
    msSmileyBtn.textContent = '😵';
    
    // Reveal all mines
    for (let r = 0; r < msRows; r++) {
        for (let c = 0; c < msCols; c++) {
            const cell = msGrid[r][c];
            const cellEl = msGridEl.children[r * msCols + c];
            if (cell.mine) {
                cellEl.classList.add('revealed');
                cellEl.textContent = '💣';
                cellEl.style.backgroundColor = '#f44336';
            }
        }
    }
}

function checkMinesweeperWin() {
    let unrevealedSafeCells = 0;
    for (let r = 0; r < msRows; r++) {
        for (let c = 0; c < msCols; c++) {
            const cell = msGrid[r][c];
            if (!cell.mine && !cell.revealed) {
                unrevealedSafeCells++;
            }
        }
    }
    
    if (unrevealedSafeCells === 0) {
        msGameOver = true;
        clearInterval(msTimerId);
        msSmileyBtn.textContent = '😎';
        msMineCountEl.textContent = '000';
        alert('تهانينا! لقد تغلبت على الألغام بنجاح! 🏆');
    }
}

// 9. Shutdown Easter Egg (BSOD)
function shutdownSite() {
    const bsod = document.getElementById('bsod-screen');
    bsod.style.display = 'block';
    
    // Add Event listener to reset site on keypress
    document.addEventListener('keydown', rebootSite);
    document.addEventListener('click', rebootSite);
}

function rebootSite() {
    document.removeEventListener('keydown', rebootSite);
    document.removeEventListener('click', rebootSite);
    location.reload();
}

// Initialization and Event Listeners Setup
document.addEventListener('DOMContentLoaded', () => {
    // Load custom site settings
    loadSiteSettings();

    // 0. Render projects (loaded from projects-data.js)
    renderProjects();

    // 1. Setup clock
    updateClock();
    setInterval(updateClock, 1000);
    
    // 2. Setup Windows Interactions
    const windows = document.querySelectorAll('.window');
    windows.forEach(win => {
        // Drag Setup
        makeWindowDraggable(win);
        
        // Focus Setup
        win.addEventListener('mousedown', () => focusWindow(win));
        win.addEventListener('touchstart', () => focusWindow(win), { passive: true });
        
        // Window Control Buttons Setup
        const btnMin = win.querySelector('.btn-min');
        const btnMax = win.querySelector('.btn-max');
        const btnClose = win.querySelector('.btn-close');
        
        if (btnMin) btnMin.addEventListener('click', (e) => { e.stopPropagation(); minimizeWindow(win); });
        if (btnMax) btnMax.addEventListener('click', (e) => { e.stopPropagation(); toggleMaximizeWindow(win); });
        if (btnClose) btnClose.addEventListener('click', (e) => { e.stopPropagation(); closeWindow(win); });
        
        // Register default open window in taskbar
        if (win.style.display !== 'none') {
            createTaskbarTab(win.id, getWindowTitle(win));
            focusWindow(win);
        }
    });
    
    // Save default CV text
    const notepadText = document.getElementById('notepad-text');
    if (notepadText) {
        defaultCVText = notepadText.value;
    }
    
    // Setup Up button for My Documents explorer navigation
    const btnDocUp = document.getElementById('btn-doc-up');
    if (btnDocUp) {
        btnDocUp.addEventListener('click', () => {
            currentFolderId = null;
            renderProjects();
        });
    }

    // 3. Desktop Icon Double Click / Click launch
    const icons = document.querySelectorAll('.desktop-icon');
    icons.forEach(icon => {
        const idMap = {
            'icon-computer': 'win-computer',
            'icon-documents': 'win-documents',
            'icon-notepad': 'win-notepad',
            'icon-ie': 'win-ie',
            'icon-minesweeper': 'win-minesweeper'
        };
        
        const targetId = idMap[icon.id];
        
        // Click focuses/opens
        icon.addEventListener('dblclick', () => {
            if (icon.id === 'icon-notepad') {
                openDefaultNotepad();
            } else {
                openWindow(targetId);
            }
        });
        
        // Touch support (double tap)
        let lastTap = 0;
        icon.addEventListener('touchend', (e) => {
            const currentTime = new Date().getTime();
            const tapLength = currentTime - lastTap;
            if (tapLength < 300 && tapLength > 0) {
                if (icon.id === 'icon-notepad') {
                    openDefaultNotepad();
                } else {
                    openWindow(targetId);
                }
                e.preventDefault();
            }
            lastTap = currentTime;
        });
    });
    
    // 4. Start Button & Start Menu
    startBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        if (startMenu.style.display === 'none') {
            startMenu.style.display = 'flex';
        } else {
            startMenu.style.display = 'none';
        }
    });
    
    // Close start menu when clicking outside
    document.addEventListener('click', () => {
        startMenu.style.display = 'none';
    });
    
    startMenu.addEventListener('click', (e) => {
        e.stopPropagation();
    });
    
    // 5. Minesweeper Reset Setup
    msSmileyBtn.addEventListener('click', () => initMinesweeper(msRows, msCols, msMines));
    
    // Initialize Minesweeper beginner version
    initMinesweeper(9, 9, 10);
});
