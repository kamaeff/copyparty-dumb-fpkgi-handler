addEventListener("DOMContentLoaded", async function() {
    ////// consts or smth; global values mb {
    const EXTS = new Set(['.pkg', '.elf', '.bin']);
    let PKGFILES;
    ////// }


    //// initial setup: file list {
    function initPage() {
        const pkgfiles = getPkgFiles();
        // const inShare = have_shr && get_evpath().startsWith(SR + have_shr)
        const leadText = in_shr ? null : 'send';
        PKGFILES = in_shr ? [] : pkgfiles;
        for (const f of pkgfiles) {
            updateLead(f, leadText);
        }
    }

    // set 'send' buttons on initial page load
    initPage();

    // hook into gentab to set up 'send' buttons during navigation
    const origgentab = treectl.gentab;
    treectl.gentab = function(top, res) {
        const ret = origgentab(top, res);
        initPage();
        return ret;
    }
    ////// }


    ////// right click menu {
    let mItem = document.createElement('a');
    mItem.id = "rfpkgi";
    mItem.textContent = 'send';
    mItem.setAttribute('href', '#');
    mItem.onclick = function(e) {
        ev(e);
        console.log(this.file);
        modal.confirm(
            `<h4>send package</h4>\n${this.file.name}`,
            () => { fetchMany([this.file]); },
            null
        );
    }
    let mItemMany = document.createElement('a');
    mItemMany.id = "rfpkgi-many";
    mItemMany.textContent = 'send selected';
    mItemMany.setAttribute('href', '#');

    let mItemAll = document.createElement('a');
    mItemAll.id = "rfpkgi-all";
    mItemAll.textContent = 'send all';
    mItemAll.setAttribute('href', '#');

    mItemMany.onclick = mItemAll.onclick = function(e) {
        ev(e);
        const message = `<h4>send (${this.files.length}) packages?</h4>\n`
                      + this.files.map(s => s.name).join('\n');
        modal.confirm(
            message,
            () => fetchMany(this.files),
            null
        );
    }

    ebi('rcm').prepend(mItemAll);
    ebi('rcm').prepend(mItemMany);
    ebi('rcm').prepend(mItem);

    const origrcm = ebi('wrap').oncontextmenu;
    ebi('wrap').oncontextmenu = function(e) {
        const mItem = ebi('rfpkgi');
        const mItemMany = ebi('rfpkgi-many');
        const mItemAll = ebi('rfpkgi-all');

        if (!PKGFILES.length) {
            for (const item of [mItem, mItemMany, mItemAll]){
                item.classList.add('hide');
            }
            return origrcm(e);
        }
        mItemAll.files = PKGFILES;
        mItemAll.textContent = `send all (${PKGFILES.length})`;
        mItemAll.classList.remove('hide');

        const fid = thegrid.en
            ? e.target.closest('#ggrid > a')?.getAttribute('ref')
            : e.target.closest('#files tbody tr')?.children[1].querySelector('a[id]').id;
        file = fid ? PKGFILES.find(f => f.id == fid) : null;
        mItem.file = file;
        if (file) {
            mItem.classList.remove('hide');
        } else {
            mItem.classList.add('hide');
        }

        const selectedFids = msel.getsel().map(f => f.id);
        const selected = PKGFILES.filter(f => selectedFids.includes(f.id));
        mItemMany.files = selected;
        mItemMany.textContent = `send selected (${selected.length})`;
        if (selected.length > 1) {
            mItemMany.classList.remove('hide');
        } else {
            mItemMany.classList.add('hide');
        }

        return origrcm(e);
    }
    ////// }


    ////// file list operations {
    function updateLead(file, toState) {
        const fid = file.id;
        const cell = ebi(fid)?.closest('tr').firstElementChild;
        if (!cell) {  // switched to another folder
            return;
        }
        if (toState === null) {
            // remove that css-added pseudo-element 'install'
            // used in shares
            cell.firstElementChild?.classList.add('fpkg-handled');
            return;
        }

        const link = document.createElement('a');
        link.setAttribute('href', '#');
        link.setAttribute('ref', fid);
        link.textContent = toState;
        link.classList.add('fpkg-handled');
        const children = [link];
        // send, approve, waiting, fail, success
        if (toState == 'send') {
            link.style.color = '#2766c4f8';
        }
        else if (toState == 'surenope') {
            link.textContent = 'sure';
            link.style.color = '#27C427f8';

            const nope = link.cloneNode();
            nope.textContent = 'nope';
            nope.style.color = '#C42727f8';
            children.push(nope);
        }
        else if (toState == '...') {
            link.style.color = 'var(--a-gray)';
        }
        else if (toState == 'fail') {
            link.style.color = '#C42727f8';
        }
        else if (toState == 'sent') {
            link.style.color = 'var(--f-gray)';
        }
        children.forEach(l => l.onclick = handleLeadClick);
        cell.replaceChildren(...children);
    }

    function handleLeadClick(e) {
        ev(e);
        const text = e.target.textContent;
        const fid = e.target.getAttribute('ref');
        const file = PKGFILES.find(f => f.id == fid);
        if (text == 'send') {
            updateLead(file, 'surenope');
        } else if (text == 'sure') {
            fetchMany([file]);
        } else if (text == 'nope' || text == 'fail') {
            updateLead(file, 'send');
        }
    }
    ////// }


    ////// sending requests to the server {
    async function doFetch(file) {
        updateLead(file, '...');
        // TODO: do we have to send it to / and not to current volume?
        // probably yes
        // but another option is to test each level
        // or to send volumes info from the server initially
        let url = SR + '/__fpkgv/sender' + file.href;
        const name = file.name;
        const ret = {success: false, message: '', file};
        try {
            const res = await fetch(url, {
                method: 'GET',
                signal: AbortSignal.timeout(3000),
            });
            const body = (await res.text()).trim();
            const hasText = body && res.headers.get('Content-Type').startsWith('text/plain');
            if (res.status != 200){
                ret.message = hasText
                            ? `error from server\n${body}`
                            : `HTTP ${res.status} ${res.statusText}`
            } else if (!body) {
                ret.message = `empty response body from server\nprobably some other handlers are enabled`;
            } else if (body != 'sent') {
                ret.message = `unexpected response from server:\n${body}`;
            } else {
                ret.success = true;
                ret.message = 'sent to the playstation';
            }
        } catch (err) {
            ret.message = `${err.message}: ${err.cause?.message}`;
        }

        updateLead(file, ret.success ? 'sent' : 'fail');
        return ret;
    }

    async function fetchMany(files) {
        const ps = {
            sent: [],
            failed: [],
        };
        for (const file of files) {
            const res = await doFetch(file);
            const timer = new Promise(r => setTimeout(r, 600));
            if (res.success) {
                ps.sent.push(res);
            } else {
                ps.failed.push(res);
            }
            toast.inf(null, `sent: ${ps.sent.length}\nfailed: ${ps.failed.length}`);
            // Goldhen can't handle too many payloads at a time
            // so give it a bit of time
            await timer;
        }

        const messages = [];
        const success = (ps.sent.length && !ps.failed.length);

        messages.push(success
            ? `<h4>FPKG send: successfully sent ${ps.sent.length}/${files.length} packages</h4>`
            : `<h4>FPKG send: failed to send ${ps.failed.length}/${files.length} packages</h4>`
        );
        for (const p of ps.failed) {
            messages.push(`😐 <strong>${p.file.name}</strong>`);
            messages.push(`<strong>ERROR:</strong> ${p.message}`);
        };
        if (ps.failed.length) {
            messages.push(`<a class="btn" id="fpkg-toast-retry">↻ retry ${ps.failed.length}</a>`)
        }
        if (!success) {
            messages.push('\n');
        }
        for (const p of ps.sent) {
            messages.push(`✅ <strong>${p.file.name}</strong> ${p.message}`);
        }

        const message = messages.join('\n');
        const t = success ? toast.ok : toast.err;
        const timeout = success ? 10 : null;
        t(timeout, message);
        console.debug({ps});
        if (ps.failed.length) {
            const retry_b = ebi('fpkg-toast-retry');
            console.debug({retry_b});
            if (retry_b) {
                retry_b.onclick = () => fetchMany(ps.failed.map(p => p.file));
            }
        }
    }
    ////// }


    ////// util {
    // yeah, now it's part of initPage(), but I prefer to keep it here in 'util' anyway
    function getPkgFiles() {
        const ret = [];
        const lsc = treectl.lsc.files.filter(f => EXTS.has('.' + f.ext.toLowerCase()));
        if (!lsc.length) return ret;
        const lsmsel = msel.getall().filter(f => !f.isd && EXTS.has(f.vp.slice(-4).toLowerCase()));
        const evpath = get_evpath().slice(SR.length);
        for (const f of lsc) {
            const nameUri = f.href.split('?')[0];
            const href = evpath + nameUri;
            const mselfile = lsmsel.find(m => m.vp.slice(SR.length) == href);
            ret.push({
                id: mselfile.id,
                name: deUri(nameUri),
                href,
            })
        }
        return ret
    }

    function deUri(href) {
        try {
            return decodeURIComponent(href);
        } catch {
            return href;
        }
    }

    ////// }
})
