(() => {
    "use strict";
    const $ = id => document.getElementById(id);
    const dialog = $("studyLibraryDialog"), opener = $("studyLibraryBtn");
    if (!dialog || !opener) return;
    const form = $("studyLibraryForm"), list = $("studyLibraryList"), status = $("studyLibraryStatus");
    const title = $("studyLibraryNoteTitle"), subject = $("studyLibrarySubject");
    const text = $("studyLibraryText"), file = $("studyLibraryFile"), enabled = $("studyLibraryEnabled");
    const badge = $("libraryComposerStatus"), suggestion = $("librarySubjectSuggestion");
    const badgeLabel = $("libraryComposerLabel"), badgeIcon = $("libraryComposerIcon");
    const badgeTooltip = $("libraryComposerTooltip");
    const addNote = $("libraryAddBtn"), back = $("libraryBackBtn");
    const uploadConfirm = $("libraryUploadConfirm"), uploadName = $("libraryUploadName");
    const uploadKeep = $("libraryUploadKeep"), uploadReplace = $("libraryUploadReplace");
    const panels = [$("libraryMyNotesPanel"), $("libraryAddNotesPanel")];
    const editForm = $("libraryEditForm"), editError = $("libraryEditError");
    const editFields = { title: $("libraryEditTitle"), subject: $("libraryEditSubject"), text: $("libraryEditText") };
    const editReload = $("libraryEditReload"), discard = $("libraryEditDiscard");
    const browse = $("libraryBrowse"), search = $("librarySearch");
    const filterSubject = $("libraryFilterSubject"), sort = $("librarySort");
    const clearFilters = $("libraryClearFilters"), resultCount = $("libraryResultCount");
    const titleOrder = new Intl.Collator("en", { sensitivity: "base", numeric: true });
    const mode = document.body.dataset.tutorMode === "science" ? "science" : "math";
    let busy = false, activeMenu = null, returnFocus = opener, statusVersion = 0;
    let editing = null, discardAction = null;
    let pendingUpload = null;
    subject.value = mode;

    function setBusy(value) {
        busy = value;
        dialog.querySelectorAll("input, select, textarea, button[type=submit], [data-library-busy], .library-note-actions button")
            .forEach(control => { control.disabled = value; });
    }
    function announce(message, suggestedSubject = null) {
        status.textContent = message;
        suggestion.hidden = !["math", "science"].includes(suggestedSubject);
        suggestion.dataset.subject = suggestedSubject || "";
        suggestion.textContent = suggestedSubject === "science" ? "Use Science" : "Use Math";
    }
    async function request(url, options = {}) {
        const response = await fetch(url, options);
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            const error = new Error(data.error || "Study Library could not complete that request.");
            error.suggestedSubject = data.suggested_subject;
            error.field = data.field;
            error.conflict = data.conflict === true;
            throw error;
        }
        return data;
    }
    async function refreshStatus() {
        const version = ++statusVersion;
        try {
            const data = await request("/library/status?subject=" + mode);
            if (version !== statusVersion) return;
            if (!Number.isInteger(data.enabled_count) || data.enabled_count < 0) throw new Error("Invalid note count.");
            const countLabel = data.enabled_count + " " + (mode === "science" ? "Science" : "Math")
                + (data.enabled_count === 1 ? " note enabled" : " notes enabled");
            const add = data.enabled_count === 0;
            badgeLabel.textContent = add ? "Add study notes" : countLabel;
            badgeIcon.hidden = !add;
            badge.dataset.view = add ? "add" : "notes";
            badge.title = countLabel + (add ? ". Add notes or select saved notes in Study Library." : ". Open Study Library.");
            badgeTooltip.textContent = "Open Study Library to " + (add ? "add or select" : "choose")
                + " saved notes for " + (mode === "science" ? "Science" : "Math") + " chats.";
            badge.setAttribute("aria-label", (add ? "Add study notes. " : "") + countLabel + ". Open Study Library");
        } catch (_) {
            if (version !== statusVersion) return;
            badgeLabel.textContent = "Notes unavailable";
            badgeIcon.hidden = true; badge.dataset.view = "notes";
            badge.title = "Open Study Library to retry.";
            badgeTooltip.textContent = "Open Study Library to retry loading your saved notes.";
            badge.setAttribute("aria-label", "Notes unavailable. Open Study Library");
        }
    }
    const notesControl = badge.closest(".notes-control");
    notesControl.addEventListener("keydown", event => {
        if (event.key === "Escape") {
            notesControl.classList.add("tooltip-dismissed");
            event.stopPropagation();
        }
    });
    for (const event of ["pointerleave", "focusout"]) {
        notesControl.addEventListener(event, () => notesControl.classList.remove("tooltip-dismissed"));
    }
    function closeMenu(focus = false) {
        if (!activeMenu) return;
        const { menu, trigger, reset } = activeMenu;
        if (menu.hasAttribute("popover") && menu.matches(":popover-open")) menu.hidePopover();
        menu.hidden = true;
        trigger.setAttribute("aria-expanded", "false");
        reset();
        activeMenu = null;
        if (focus && trigger.isConnected) trigger.focus({ preventScroll: true });
    }
    function activate(index, focus = false) {
        closeMenu();
        panels.forEach((panel, i) => { panel.hidden = i !== index; });
        back.hidden = index === 0 && !editing;
        addNote.hidden = index !== 0 || Boolean(editing);
        dialog.scrollTo({ top: 0, behavior: "instant" });
        if (focus) (index === 1 ? pendingUpload ? uploadKeep : $("libraryUploadBtn") : search).focus();
    }
    addNote.addEventListener("click", () => {
        if (busy || editing) return;
        activate(1, true); announce("");
    });
    back.addEventListener("click", () => {
        if (busy) return;
        if (editing) requestDiscard("cancel");
        else { activate(0, true); announce(""); }
    });
    function button(label) {
        const element = document.createElement("button");
        element.type = "button";
        element.textContent = label;
        return element;
    }
    function setAction(element, label, icon) {
        const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
        svg.classList.add("tool-icon");
        svg.setAttribute("aria-hidden", "true");
        const use = document.createElementNS(svg.namespaceURI, "use");
        use.setAttribute("href", "/static/vendor/lucide/sidebar.svg#" + icon);
        svg.append(use);
        element.replaceChildren(svg, document.createTextNode(label));
    }
    function isEditDirty() {
        return editing && Object.entries(editFields).some(([key, field]) => field.value !== editing[key]);
    }
    function isNewDraftDirty() {
        return Boolean(title.value.trim() || text.value.trim());
    }
    function showEditError(message = "", field = null) {
        editError.textContent = message;
        Object.entries(editFields).forEach(([key, input]) => {
            if (key === field) input.setAttribute("aria-invalid", "true");
            else input.removeAttribute("aria-invalid");
        });
    }
    function fillEditor(note) {
        editing = note;
        replaceSavedRow(note);
        Object.entries(editFields).forEach(([key, field]) => { field.value = note[key]; });
        editForm.hidden = false;
        browse.hidden = true;
        list.hidden = true;
        discard.hidden = true; discardAction = null; editReload.hidden = true;
        showEditError();
        activate(0);
        updateDuplicates();
    }
    function replaceSavedRow(note) {
        const old = Array.from(list.children).find(item => item.dataset.noteId === note.id);
        const row = renderNote(note);
        if (old) old.replaceWith(row);
        updateEmpty();
    }
    async function latestNote(id) {
        const data = await request("/library/notes");
        const note = data.notes.find(item => item.id === id);
        if (!note) throw new Error("That note was deleted. Your draft is still here.");
        return note;
    }
    async function startEdit(note) {
        if (busy) return;
        closeMenu(); setBusy(true);
        try {
            fillEditor(await latestNote(note.id));
            setBusy(false); editFields.title.focus(); announce("");
        } catch (error) { announce(error.message); }
        finally { setBusy(false); }
    }
    function finishEdit() {
        const id = editing.id;
        editing = null; editForm.hidden = true; list.hidden = false;
        browse.hidden = false;
        activate(0);
        discard.hidden = true; discardAction = null; showEditError(); updateEmpty();
        const row = Array.from(list.children).find(item => item.dataset.noteId === id);
        (row && !row.hidden ? row.querySelector(".library-actions-trigger") : search).focus();
    }
    async function performDiscard(action) {
        if (action === "cancel") { finishEdit(); return; }
        setBusy(true);
        try {
            fillEditor(await latestNote(editing.id));
            setBusy(false); editFields.title.focus(); announce("Latest saved note loaded.");
        } catch (error) { showEditError(error.message); }
        finally { setBusy(false); }
    }
    function requestDiscard(action) {
        if (busy || !editing) return;
        if (!isEditDirty()) { performDiscard(action); return; }
        discardAction = action; discard.hidden = false;
        $("libraryEditKeep").focus();
    }
    $("libraryEditCancel").addEventListener("click", () => requestDiscard("cancel"));
    editReload.addEventListener("click", () => requestDiscard("reload"));
    $("libraryEditKeep").addEventListener("click", () => {
        discard.hidden = true; discardAction = null; editFields.text.focus();
    });
    $("libraryEditConfirmDiscard").addEventListener("click", () => {
        if (!busy && discardAction) performDiscard(discardAction);
    });
    editForm.addEventListener("submit", async event => {
        event.preventDefault();
        if (busy || !editing) return;
        setBusy(true); showEditError();
        const id = editing.id;
        try {
            const result = await request("/library/notes/" + encodeURIComponent(id), {
                method: "PATCH", headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ title: editFields.title.value, subject: editFields.subject.value,
                    text: editFields.text.value, revision: editing.revision }),
            });
            // Replace the saved row without refetching or disturbing the separate Add Notes draft.
            replaceSavedRow(result.note);
            setBusy(false); finishEdit(); refreshStatus(); announce("Note updated.");
        } catch (error) {
            showEditError(error.message, error.field);
            if (error.conflict) editReload.hidden = false;
            setBusy(false);
            if (editFields[error.field]) editFields[error.field].focus();
        } finally { setBusy(false); }
    });
    window.addEventListener("beforeunload", event => {
        if (isEditDirty() || isNewDraftDirty()) { event.preventDefault(); event.returnValue = ""; }
    });
    function renderNote(note) {
        const row = document.createElement("li"), heading = document.createElement("div");
        row.className = "library-note-card";
        row.dataset.noteId = note.id;
        row.libraryNote = note;
        heading.className = "library-note-heading";
        const info = document.createElement("div"), name = document.createElement("strong");
        name.id = "library-note-name-" + note.id;
        name.textContent = note.title;
        const metadata = document.createElement("div");
        metadata.className = "library-note-metadata";
        const area = document.createElement("span");
        area.className = "library-note-subject";
        area.textContent = note.subject === "both" ? "Both tutors" : note.subject === "science" ? "Science" : "Math";
        metadata.append(area);
        info.append(name, metadata);
        const updated = document.createElement("time");
        updated.className = "library-note-updated";
        const timestamp = noteTime(note);
        if (timestamp) {
            const date = new Date(timestamp);
            updated.dateTime = date.toISOString();
            updated.textContent = "Updated " + date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
            updated.title = date.toLocaleString();
            metadata.append(updated);
        }
        const actions = document.createElement("div");
        actions.className = "library-note-actions";
        const trigger = button("");
        setAction(trigger, "", "ellipsis");
        trigger.className = "library-actions-trigger";
        trigger.setAttribute("aria-label", "Actions for " + note.title);
        trigger.title = "Note actions";
        trigger.setAttribute("aria-haspopup", "menu");
        trigger.setAttribute("aria-expanded", "false");
        const menu = document.createElement("div");
        menu.className = "library-action-menu";
        menu.id = "library-menu-" + note.id;
        menu.hidden = true;
        menu.setAttribute("role", "menu");
        menu.setAttribute("aria-label", "Actions for " + note.title);
        trigger.setAttribute("aria-controls", menu.id);
        if (typeof menu.showPopover === "function") menu.setAttribute("popover", "manual");
        const previewButton = button("Preview"), renameButton = button("Rename"), remove = button("Delete");
        const editButton = button("Edit note");
        setAction(previewButton, "Preview", "eye");
        setAction(renameButton, "Rename", "pencil-line");
        setAction(editButton, "Edit note", "clipboard-check");
        setAction(remove, "Delete", "trash-2");
        remove.classList.add("is-danger");
        const items = [previewButton, renameButton, editButton, remove];
        items.forEach(item => { item.setAttribute("role", "menuitem"); item.tabIndex = -1; });
        menu.append(...items);
        actions.append(trigger, menu);
        heading.append(info, actions);
        const selection = document.createElement("label");
        selection.className = "library-enabled";
        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.checked = Boolean(note.enabled);
        checkbox.setAttribute("aria-label", "Use " + note.title + " for future answers");
        const selectionState = document.createElement("span");
        selectionState.className = "library-selection-state";
        selectionState.textContent = checkbox.checked ? "On" : "Off";
        selection.append(checkbox, selectionState, document.createTextNode("Use this note"));
        const subjectHint = document.createElement("p");
        subjectHint.className = "library-subject-hint";
        subjectHint.hidden = note.subject === mode || note.subject === "both";
        subjectHint.textContent = (note.subject === "science" ? "Science" : "Math")
            + " notes are searched only in the " + (note.subject === "science" ? "Science" : "Math") + " tutor.";
        const excerpt = document.createElement("p");
        excerpt.className = "library-note-excerpt";
        const excerptText = Array.from(String(note.text || "").replace(/\s+/g, " ").trim());
        excerpt.textContent = excerptText.slice(0, 220).join("") + (excerptText.length > 220 ? "..." : "");
        const footer = document.createElement("div");
        footer.className = "library-note-footer";
        const previewToggle = button("");
        previewToggle.className = "library-preview-toggle";
        previewToggle.dataset.libraryBusy = "";
        previewToggle.setAttribute("aria-expanded", "false");
        previewToggle.setAttribute("aria-label", "Preview note: " + note.title);
        previewToggle.title = "Preview note: " + note.title;
        setAction(previewToggle, "Preview note", "eye");
        const preview = document.createElement("div");
        preview.className = "library-note-preview";
        preview.id = "library-preview-" + note.id;
        preview.tabIndex = 0;
        preview.setAttribute("role", "region");
        preview.setAttribute("aria-labelledby", name.id);
        previewToggle.setAttribute("aria-controls", preview.id);
        preview.hidden = true;
        const body = document.createElement("p");
        body.textContent = note.text;
        preview.append(body);
        footer.append(selection, previewToggle);
        function setPreview(open) {
            closeMenu();
            preview.hidden = !open;
            if (open) preview.scrollTop = 0;
            excerpt.hidden = open;
            previewToggle.setAttribute("aria-expanded", String(open));
            previewToggle.setAttribute("aria-label", (open ? "Close preview: " : "Preview note: ") + note.title);
            previewToggle.title = (open ? "Close preview: " : "Preview note: ") + note.title;
            setAction(previewToggle, open ? "Close preview" : "Preview note", open ? "eye-off" : "eye");
        }
        previewToggle.addEventListener("click", () => setPreview(preview.hidden));
        const editor = document.createElement("form");
        editor.className = "library-rename-form";
        editor.hidden = true;
        const label = document.createElement("label"), input = document.createElement("input");
        input.id = "library-title-" + note.id;
        input.required = true;
        input.maxLength = 80;
        input.value = note.title;
        label.htmlFor = input.id;
        label.textContent = "Note title";
        const save = button("Save title"), cancel = button("Cancel");
        save.type = "submit";
        editor.append(label, input, save, cancel);
        let confirming = false;
        const reset = () => { confirming = false; setAction(remove, "Delete", "trash-2"); };
        function openMenu(last = false) {
            closeMenu();
            menu.hidden = false;
            if (menu.hasAttribute("popover")) {
                menu.showPopover();
                const rect = trigger.getBoundingClientRect();
                const width = menu.offsetWidth, height = menu.offsetHeight;
                menu.style.left = Math.max(8, Math.min(rect.right - width, innerWidth - width - 8)) + "px";
                const preferred = rect.bottom + height + 8 <= innerHeight ? rect.bottom + 4 : rect.top - height - 4;
                menu.style.top = Math.max(8, Math.min(preferred, innerHeight - height - 8)) + "px";
            } else if (typeof window.positionToolMenu === "function") {
                window.positionToolMenu(menu, trigger, 190);
            }
            const headerBottom = dialog.querySelector(".study-library-header").getBoundingClientRect().bottom;
            const minTop = Math.max(8, Math.min(headerBottom + 4, innerHeight - 52));
            menu.style.maxHeight = `${Math.max(44, innerHeight - minTop - 8)}px`;
            const menuRect = menu.getBoundingClientRect();
            const top = Math.max(minTop, Math.min(menuRect.top, innerHeight - menuRect.height - 8));
            menu.style.top = `${(parseFloat(menu.style.top) || 0) + top - menuRect.top}px`;
            trigger.setAttribute("aria-expanded", "true");
            const anchor = trigger.getBoundingClientRect();
            activeMenu = { menu, trigger, reset, top: anchor.top, left: anchor.left };
            focusItem(items[last ? items.length - 1 : 0]);
        }
        function focusItem(item) {
            if (typeof window.focusToolMenuItem === "function") window.focusToolMenuItem(item, menu);
            else item.focus();
        }
        trigger.addEventListener("click", () => activeMenu && activeMenu.trigger === trigger ? closeMenu(true) : openMenu());
        trigger.addEventListener("keydown", event => {
            if (!["ArrowDown", "ArrowUp"].includes(event.key)) return;
            event.preventDefault();
            openMenu(event.key === "ArrowUp");
        });
        menu.addEventListener("keydown", event => {
            if (event.key === "Escape") {
                event.preventDefault(); event.stopPropagation(); closeMenu(true); return;
            }
            if (event.key === "Tab") { closeMenu(true); return; }
            const index = items.indexOf(document.activeElement);
            const next = { ArrowDown: (index + 1) % items.length, ArrowUp: (index + items.length - 1) % items.length, Home: 0, End: items.length - 1 }[event.key];
            if (next !== undefined) { event.preventDefault(); focusItem(items[next]); }
        });
        previewButton.addEventListener("click", () => {
            setPreview(true); previewToggle.focus();
        });
        renameButton.addEventListener("click", () => {
            closeMenu(); editor.hidden = false; input.value = note.title; input.focus(); input.select();
        });
        editButton.addEventListener("click", () => startEdit(note));
        cancel.addEventListener("click", () => { editor.hidden = true; trigger.focus(); });
        const endpoint = "/library/notes/" + encodeURIComponent(note.id);
        checkbox.addEventListener("change", async () => {
            if (busy) return;
            setBusy(true);
            try {
                await request(endpoint, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ enabled: checkbox.checked }) });
                note.enabled = checkbox.checked;
                selectionState.textContent = checkbox.checked ? "On" : "Off";
                announce(checkbox.checked ? "Note enabled." : "Note disabled for future searches.");
                refreshStatus();
            } catch (error) { checkbox.checked = Boolean(note.enabled); announce(error.message); }
            finally { setBusy(false); }
        });
        editor.addEventListener("submit", async event => {
            event.preventDefault();
            if (busy) return;
            setBusy(true);
            try {
                const result = await request(endpoint, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title: input.value }) });
                setBusy(false);
                replaceSavedRow(result.note || { ...note, title: input.value.trim() });
                const replacement = Array.from(list.children).find(item => item.dataset.noteId === note.id);
                (replacement && !replacement.hidden ? replacement.querySelector(".library-actions-trigger") : search).focus();
                announce("Note renamed.");
            } catch (error) { announce(error.message); }
            finally { setBusy(false); }
        });
        remove.addEventListener("click", async () => {
            if (busy) return;
            if (!confirming) {
                confirming = true; setAction(remove, "Confirm delete", "trash-2");
                announce("Delete this saved note? Earlier chat excerpts will remain.");
                return;
            }
            setBusy(true);
            try {
                await request(endpoint, { method: "DELETE" });
                closeMenu(); row.remove();
                updateEmpty(); search.focus();
                announce("Note deleted. It will not be searched again."); refreshStatus();
            } catch (error) { announce(error.message); }
            finally { setBusy(false); }
        });
        row.append(heading, excerpt, subjectHint, footer, preview, editor);
        list.append(row);
        return row;
    }
    function updateEmpty() {
        closeMenu();
        const old = list.querySelector(".library-empty");
        if (old) old.remove();
        const rows = Array.from(list.children);
        const terms = search.value.normalize("NFC").toLocaleLowerCase().trim().split(/\s+/).filter(Boolean);
        const filtered = terms.length > 0 || filterSubject.value !== "all";
        rows.sort((a, b) => {
            const recent = sort.value === "updated" ? noteTime(b.libraryNote) - noteTime(a.libraryNote) : 0;
            return recent || titleOrder.compare(a.libraryNote.title, b.libraryNote.title)
                || a.dataset.noteId.localeCompare(b.dataset.noteId);
        });
        let visible = 0;
        rows.forEach(row => {
            const note = row.libraryNote;
            const content = (note.title + "\n" + note.text).normalize("NFC").toLocaleLowerCase();
            row.hidden = !(filterSubject.value === "all" || note.subject === filterSubject.value)
                || !terms.every(term => content.includes(term));
            if (!row.hidden) visible++;
            list.append(row);
        });
        const empty = !rows.length;
        clearFilters.hidden = !filtered;
        resultCount.textContent = filtered ? visible + " of " + rows.length + " notes"
            : rows.length + (rows.length === 1 ? " saved note" : " saved notes");
        if (visible === 0) {
            const row = document.createElement("li");
            row.className = "library-empty";
            row.textContent = empty ? "No saved notes." : "No matching notes.";
            list.append(row);
        }
        updateDuplicates();
    }
    function noteTime(note) {
        const value = note.updated_at || note.created_at;
        if (!value) return 0;
        const utc = value.endsWith("Z") ? value : value.replace(" ", "T") + "Z";
        return Date.parse(utc) || 0;
    }
    function updateDuplicates() {
        const normalize = value => value.trim().replace(/\r\n?/g, "\n");
        const notes = Array.from(list.children).map(row => row.libraryNote).filter(Boolean);
        for (const [field, notice, except] of [[text, $("libraryAddDuplicate"), null],
            [editFields.text, $("libraryEditDuplicate"), editing?.id]]) {
            const content = normalize(field.value);
            const duplicate = content && notes.find(note => note.id !== except && normalize(note.text) === content);
            notice.hidden = !duplicate;
            notice.textContent = duplicate ? 'This text is already saved as "' + duplicate.title + '". You can still save a copy.' : "";
        }
    }
    search.addEventListener("input", updateEmpty);
    filterSubject.addEventListener("change", updateEmpty);
    sort.addEventListener("change", updateEmpty);
    clearFilters.addEventListener("click", () => {
        search.value = ""; filterSubject.value = "all"; updateEmpty(); search.focus();
    });
    text.addEventListener("input", updateDuplicates);
    editFields.text.addEventListener("input", updateDuplicates);
    async function load() {
        const data = await request("/library/notes");
        closeMenu(); list.replaceChildren();
        data.notes.forEach(renderNote); updateEmpty(); refreshStatus();
    }
    async function open(source, view = 0) {
        if (document.querySelector(".ai-settings-modal:not([hidden]), .delete-chat-modal:not([hidden])")) return;
        returnFocus = source;
        if (!busy) activate(editing ? 0 : view);
        if (!dialog.open) {
            window.dispatchEvent(new Event("workspace-modal-opening"));
            dialog.showModal();
        }
        // Reopening must not unlock the form while an earlier request still owns it.
        if (busy) return;
        setBusy(true); announce("Loading notes...");
        try {
            await load(); announce("");
            setBusy(false);
            if (!editing && dialog.open) {
                (panels[1].hidden ? search : pendingUpload ? uploadKeep : $("libraryUploadBtn")).focus();
            }
        }
        catch (error) { announce(error.message); }
        finally { setBusy(false); }
    }
    opener.addEventListener("click", () => open(opener));
    badge.addEventListener("click", () => open(badge, badge.dataset.view === "add" ? 1 : 0));
    window.addEventListener("study-library-add", event => {
        open(event.detail?.source instanceof HTMLElement ? event.detail.source : opener, 1);
    });
    $("closeStudyLibrary").addEventListener("click", () => dialog.close());
    dialog.addEventListener("cancel", event => {
        if (pendingUpload && !panels[1].hidden) {
            event.preventDefault();
            keepUploadDraft();
        }
    });
    dialog.addEventListener("close", () => { closeMenu(); returnFocus.focus(); });
    document.addEventListener("click", event => {
        if (activeMenu && !activeMenu.menu.contains(event.target) && !activeMenu.trigger.contains(event.target)) closeMenu();
    });
    window.addEventListener("resize", () => {
        closeMenu(true);
        keepUploadChoicesVisible();
    });
    dialog.addEventListener("scroll", () => {
        if (!activeMenu) return;
        const rect = activeMenu.trigger.getBoundingClientRect();
        // Ignore a queued focus scroll when the menu already uses the final anchor position.
        if (Math.abs(rect.top - activeMenu.top) > 1 || Math.abs(rect.left - activeMenu.left) > 1) closeMenu(true);
    });
    $("libraryUploadBtn").addEventListener("click", () => file.click());
    $("libraryPasteBtn").addEventListener("click", () => text.focus());
    suggestion.addEventListener("click", () => { subject.value = suggestion.dataset.subject; announce("Subject changed. Check your note, then save it."); });
    subject.addEventListener("change", () => announce(""));
    function clearPendingUpload() {
        pendingUpload = null;
        uploadConfirm.hidden = true;
        uploadName.textContent = "";
    }
    function keepUploadDraft() {
        clearPendingUpload();
        announce("Your unfinished note was kept.");
        (text.value.trim() ? text : title).focus();
    }
    function keepUploadChoicesVisible() {
        if (pendingUpload && dialog.open && !panels[1].hidden
                && [uploadKeep, uploadReplace].includes(document.activeElement)) {
            uploadKeep.parentElement.scrollIntoView({ block: "nearest" });
        }
    }
    uploadKeep.addEventListener("focus", keepUploadChoicesVisible);
    uploadReplace.addEventListener("focus", keepUploadChoicesVisible);
    uploadKeep.addEventListener("click", keepUploadDraft);
    uploadReplace.addEventListener("click", () => {
        if (busy || !pendingUpload) return;
        const selected = pendingUpload;
        clearPendingUpload();
        loadFilePreview(selected);
    });
    function previewFile(selected) {
        if (!selected || busy) return;
        // Allow selecting the same file again after cancelling or a failed preview.
        file.value = "";
        clearPendingUpload();
        if (selected.size > 4 * 1024 * 1024) { announce("Choose a document no larger than 4 MiB."); return; }
        if (isNewDraftDirty()) {
            pendingUpload = selected;
            uploadName.textContent = selected.name;
            uploadConfirm.hidden = false;
            announce("Choose whether to replace your unfinished note.");
            uploadKeep.focus();
            return;
        }
        loadFilePreview(selected);
    }
    async function loadFilePreview(selected) {
        const data = new FormData(); data.append("file", selected);
        setBusy(true); announce("Preparing preview...");
        try {
            const result = await request("/library/preview", { method: "POST", body: data });
            if (!result || typeof result.title !== "string" || typeof result.text !== "string") {
                throw new Error("That document preview could not be read. Your note has not changed.");
            }
            title.value = result.title.replace(/\.[^.]+$/, "").replace(/[_-]+/g, " ").trim().slice(0, 80);
            text.value = result.text;
            updateDuplicates();
            announce("Preview ready. Check the text and subject before saving.");
        } catch (error) { announce(error.message); }
        finally { file.value = ""; setBusy(false); }
    }
    file.addEventListener("change", () => previewFile(file.files[0]));
    const dropzone = $("libraryDropzone");
    ["dragenter", "dragover"].forEach(type => dropzone.addEventListener(type, event => {
        event.preventDefault(); if (!busy) dropzone.classList.add("is-dragging");
    }));
    dropzone.addEventListener("dragleave", event => { if (!dropzone.contains(event.relatedTarget)) dropzone.classList.remove("is-dragging"); });
    dropzone.addEventListener("drop", event => {
        event.preventDefault(); dropzone.classList.remove("is-dragging");
        if (busy) return;
        const files = event.dataTransfer.files;
        if (files.length !== 1) { announce("Upload one document at a time."); return; }
        previewFile(files[0]);
    });
    form.addEventListener("submit", async event => {
        event.preventDefault(); if (busy) return;
        setBusy(true);
        try {
            const saved = await request("/library/notes", { method: "POST", headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ title: title.value, subject: subject.value, text: text.value, enabled: enabled.checked }) });
            title.value = ""; text.value = ""; enabled.checked = true;
            clearPendingUpload();
            activate(0);
            try {
                await load(); setBusy(false); announce("Note saved.");
                if (dialog.open && !panels[0].hidden) {
                    const row = Array.from(list.children).find(item => item.dataset.noteId === saved.id);
                    (row && !row.hidden ? row.querySelector(".library-actions-trigger") : search).focus();
                }
            }
            catch (_) { announce("Note saved, but the list could not refresh. Reopen Study Library."); refreshStatus(); }
        } catch (error) { announce(error.message, error.suggestedSubject); }
        finally { setBusy(false); }
    });
    window.addEventListener("focus", refreshStatus);
    refreshStatus();
})();
