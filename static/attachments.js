/* Composer files stay in memory until the user sends or removes them. */
(() => {
    const button = document.getElementById("attachmentBtn");
    const menu = document.getElementById("attachmentMenu");
    const tray = document.getElementById("attachmentTray");
    const input = document.getElementById("userInput");
    if (!button || !menu || !tray) return;
    const photoInput = document.getElementById("attachmentPhotoInput");
    const photoButton = document.getElementById("addPhotoBtn");
    const fileInput = document.getElementById("attachmentFileInput");
    const photos = new Set(["jpg", "jpeg", "png", "webp"]);
    const documents = new Set(["txt", "md", "csv", "json", "pdf", "docx"]);
    let files = [];
    let locked = false;

    function warn(message) {
        window.dispatchEvent(new CustomEvent("attachment-warning", { detail: message }));
    }

    function setOpen(open, focus = false) {
        menu.hidden = !open;
        button.setAttribute("aria-expanded", String(open));
        if (open && typeof window.positionToolMenu === "function") {
            window.positionToolMenu(menu, button, 208);
        }
        if (open && focus) menu.querySelector("button").focus();
    }
    window.addEventListener("workspace-modal-opening", () => setOpen(false));
    window.addEventListener("resize", () => setOpen(false));

    function render() {
        tray.replaceChildren();
        tray.hidden = files.length === 0;
        for (const entry of files) {
            const item = document.createElement("div");
            item.className = "attachment-chip";
            if (entry.url) {
                const image = document.createElement("img");
                image.src = entry.url;
                image.alt = "Selected photo preview";
                item.append(image);
            }
            const name = document.createElement("span");
            name.textContent = entry.file.name;
            name.title = entry.file.name;
            const remove = document.createElement("button");
            remove.type = "button";
            remove.textContent = "x";
            remove.title = `Remove ${entry.file.name}`;
            remove.setAttribute("aria-label", `Remove ${entry.file.name}`);
            remove.disabled = locked;
            remove.addEventListener("click", () => {
                if (locked) return;
                if (entry.url) URL.revokeObjectURL(entry.url);
                files = files.filter(value => value !== entry);
                render();
                button.focus();
            });
            item.append(name, remove);
            tray.append(item);
        }
        if (files.length) {
            const privacy = document.createElement("p");
            privacy.className = "attachment-privacy";
            privacy.textContent = "Sent to your AI provider and saved with this chat. Avoid private information.";
            tray.append(privacy);
        }
    }

    function add(selected) {
        if (locked) return;
        for (const file of selected) {
            const extension = file.name.split(".").pop().toLowerCase();
            if (!photos.has(extension) && !documents.has(extension)) {
                warn("Supported files: JPG, PNG, WebP, TXT, MD, CSV, JSON, PDF, and DOCX.");
                continue;
            }
            if (!file.size || file.size > 4 * 1024 * 1024) {
                warn("Choose a nonempty file under 4 MiB.");
                continue;
            }
            if (files.some(entry => entry.file.name === file.name && entry.file.size === file.size
                && entry.file.lastModified === file.lastModified)) continue;
            if (files.length >= 3) {
                warn("Attach at most 3 files per message.");
                break;
            }
            files.push({ file, url: photos.has(extension) ? URL.createObjectURL(file) : null });
        }
        render();
        if (files.length) window.dispatchEvent(new Event("attachment-selected"));
        input.focus();
    }

    function clear() {
        files.forEach(entry => { if (entry.url) URL.revokeObjectURL(entry.url); });
        files = [];
        setOpen(false);
        render();
    }

    button.addEventListener("click", () => setOpen(menu.hidden, true));
    photoButton?.addEventListener("click", () => {
        if (locked) return;
        setOpen(false);
        photoInput.click();
    });
    menu.addEventListener("click", event => {
        if (event.target.closest("[data-study-library-add]")) {
            if (locked) return;
            setOpen(false);
            window.dispatchEvent(new CustomEvent("study-library-add", { detail: { source: button } }));
            return;
        }
        const kind = event.target.closest("[data-attachment-kind]")?.dataset.attachmentKind;
        if (!kind || locked) return;
        setOpen(false);
        (kind === "photo" ? photoInput : fileInput).click();
    });
    for (const fileInputElement of [photoInput, fileInput]) {
        fileInputElement.addEventListener("change", () => {
            add(Array.from(fileInputElement.files));
            fileInputElement.value = "";
        });
    }
    document.addEventListener("click", event => {
        if (!event.target.closest(".attachment-picker")) setOpen(false);
    });
    document.addEventListener("keydown", event => {
        if (menu.hidden) return;
        if (event.key === "Escape") {
            event.preventDefault();
            event.stopPropagation();
            setOpen(false);
            button.focus();
        } else if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
            event.preventDefault();
            const options = [...menu.querySelectorAll("button")];
            const index = options.indexOf(document.activeElement);
            const next = event.key === "Home" ? 0 : event.key === "End" ? options.length - 1
                : (index + (event.key === "ArrowUp" ? -1 : 1) + options.length) % options.length;
            options[next].focus();
        }
    });
    menu.addEventListener("focusout", () => {
        requestAnimationFrame(() => {
            if (!menu.contains(document.activeElement) && document.activeElement !== button) setOpen(false);
        });
    });
    input.addEventListener("paste", event => {
        const pasted = [...(event.clipboardData?.files || [])];
        if (pasted.length) {
            event.preventDefault();
            add(pasted);
        }
    });
    window.addEventListener("pagehide", clear);
    window.DelphicAttachments = {
        hasFiles: () => files.length > 0,
        summaries: () => files.map(entry => ({ name: entry.file.name, kind: entry.url ? "image" : "document" })),
        buildRequest: payload => {
            if (!files.length) return { headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) };
            const body = new FormData();
            body.append("payload", JSON.stringify(payload));
            files.forEach(entry => body.append("files", entry.file));
            return { body };
        },
        clear,
        setBusy: busy => {
            locked = busy;
            button.disabled = busy;
            if (photoButton) photoButton.disabled = busy;
            if (busy) setOpen(false);
            render();
        },
    };
})();
