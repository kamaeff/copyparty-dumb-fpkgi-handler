addEventListener("DOMContentLoaded", async function() {
    ////// consts {
    const EXTS = new Set(['.pkg', '.elf', '.bin']);
    ////// }


    ////// initial setup: file list {
    // set 'install' buttons on initial page load
    for (const f of getPkgFiles()) {
        updateLead(f.id, 'install');
    }
    // hook into gentab to set up 'install' buttons during navigation
    const origgentab = treectl.gentab;
    treectl.gentab = function(top, res) {
        const resp = origgentab(top, res);
        for (const f of getPkgFiles()) {
            updateLead(f.id, 'install');
        }
        return resp;
    }
    ////// }


    ////// file grid: right click menu {
    let mItem = document.createElement('a');
    mItem.id = "rfpkgi";
    mItem.textContent = 'install';
    mItem.setAttribute('href', '#');
    mItem.onclick = function(e) {
        ev(e);
        console.log(this.fid);
        const message = 
        modal.confirm(
            `<h4>install package</h4>\n${deUri(nameHref(hrefById(this.fid)))}`,
            () => { fetchOne(this.fid); },
            null
        );
    }
    let mItemMany = document.createElement('a');
    mItemMany.id = "rfpkgi-many";
    mItemMany.textContent = 'install selected';
    mItemMany.setAttribute('href', '#');
    mItemMany.onclick = function(e) {
        ev(e);
        console.log(this.fselected);
        const message = `<h4>install (${this.fselected.length}) packages?</h4>\n`
                      + this.fselected.map(s => deUri(s.href)).join('\n');
        modal.confirm(
            message,
            () => fetchMany(this.fselected.map(f => f.id)),
            null
        );
    }
    ebi('rcm').prepend(mItemMany);
    ebi('rcm').prepend(mItem);

    const origrcm = ebi('wrap').oncontextmenu;
    ebi('wrap').oncontextmenu = function(e) {
        const mItem = ebi('rfpkgi');
        const mItemMany = ebi('rfpkgi-many');
        const link = thegrid.en
            ? e.target.closest('#ggrid > a')
            : e.target.closest('#files tbody tr')?.children[1].querySelector('a[id]');
        if (isInstallable(nameHref(link?.getAttribute('href')))) {
            mItem.fid = thegrid.en ? link.getAttribute('ref') : link.id;
            mItem.classList.remove('hide');
        } else {
            mItem.classList.add('hide');
            mItem.fid = null;
        }

        const selected = getPkgFiles(true);
        mItemMany.fselected = selected;
        mItemMany.textContent = `install selected (${selected.length})`
        if (selected.length > 1) {
            mItemMany.classList.remove('hide');
        } else {
            mItemMany.classList.add('hide');
        }
        return origrcm(e);
    }
    ////// }


    ////// file list operations {
    function updateLead(fid, toState) {
        const cell = ebi(fid).closest('tr').firstElementChild;
        const link = document.createElement('a');
        link.setAttribute('href', '#');
        link.setAttribute('ref', fid);
        link.textContent = toState;
        link.classList.add('fpkg-handled');
        const children = [link];
        // install, approve, waiting, fail, success
        if (toState == 'install') {
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
        else if (toState == 'failed') {
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
        if (text == "install") {
            updateLead(fid, "surenope");
        } else if (text == "sure") {
            fetchOne(fid);
        } else if (text == "nope" || text == "failed") {
            updateLead(fid, "install");
        }
    }
    ////// }


    ////// sending requests to the server {
    function doFetch(fid) {
        updateLead(fid, "...");
        const href = nameHref(hrefById(fid));
        const name = deUri(href);
        
        return fetch('.', {
            method: 'POST',
            body: 'msg=fpkg-install:' + href,
            signal: AbortSignal.timeout(3000),
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'
            },
        }).then(
            async (res) => {
                if (res.status < 200 || res.status >= 400) {
                    return {
                        success: false,
                        message: `HTTP ${res.status} ${res.statusText}`
                    }
                }
                const body = (await res.text()).trim();
                if (!body) {
                    return {
                        success: false,
                        message: `empty response body from server\nprobably some other hooks are enabled`
                    }
                }
                if (body != 'sent') {
                    return {
                        success: false,
                        message: `error from server:\n${body}`
                    }
                }
                return {
                    success: true,
                    message: 'sent to the playstation'
                }
            },
            (err) => {
                return {
                    success: false,
                    message: `${err.message}: ${err.cause?.message}`
                }
            }
        ).then(res => {
            const state = res.success ? 'sent' : 'failed';
            updateLead(fid, state);
            res.fid = fid;
            res.name = name;
            return res;
        });
    }

    function fetchOne(fid) {
        return doFetch(fid).then(res => {
            console.log(res);
            if (res.success) {
                toast.ok(5, `<b>FPKG install success</b>\n${res.name}\n${res.message}`);
            } else {
                toast.err(null, `<h4>FPKG install failed</h4>\n${res.name}\n${res.message}`);
            }
        });
    }

    function fetchMany(fids) {
        const ps = {
            sent: [],
            failed: [],
        };
        const results = fids.map(fid => doFetch(fid).then(res => {
            if (res.success) {
                ps.sent.push(res);
            } else {
                ps.failed.push(res);
            }
            toast.inf(null, `sent: ${ps.sent.length}\nfailed: ${ps.failed.length}`);
        }));
        Promise.allSettled(results).then(() => {
            const messages = [];
            const success = (ps.sent.length && !ps.failed.length);

            messages.push(success
                ? `<h4>FPKG install: successfully sent ${ps.sent.length}/${fids.length} packages</h4>`
                : `<h4>FPKG install: failed to send ${ps.failed.length}/${fids.length} packages</h4>`
            );
            for (const p of ps.failed) {
                messages.push(`😐 <strong>${p.name}</strong>`);
                messages.push(`<strong>ERROR:</strong> ${p.message}`);
            };
            if (!success) {
                messages.push('\n');
            }
            for (const p of ps.sent) {
                messages.push(`✅ <strong>${p.name}</strong> ${p.message}`);
            }
            const message = messages.join('\n');
            const t = success ? toast.ok : toast.err;
            const timeout = success ? 10 : null;
            t(timeout, message);
        })
    }
    ////// }


    ////// util {
    function isInstallable(name) {
        return EXTS.has(name?.slice(-4)?.toLowerCase())
    }
    function getPkgFiles(selected) {
        const res = [];
        const files = selected ? msel.getsel() : msel.getall()
        for (const f of files) {
            if (!f.isd && isInstallable(f.vp)) {
                const href = f.vp.slice(f.vp.lastIndexOf('/') + 1);
                console.log(href);
                res.push({id: f.id, href});
            }
        }
        return res;
    }

    function hrefById(fid) {
        return ebi(fid).getAttribute('href')
    }

    function deUri(href) {
        try {
            return decodeURIComponent(href);
        } catch {
            return href;
        }
    }

    function nameHref(fullHref) {
        return fullHref?.split('?')[0].split('/').at(-1);
    }
    ////// }
})
