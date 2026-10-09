"""Injected before viewer modules execute, so initialization errors are captured."""

PDFJS_DIAGNOSTICS_JS = r"""(() => {
    if (window.__freepdfDiagnostics) return;
    const state = window.__freepdfDiagnostics = {
        stage: 'document_created', documentLoaded: false, firstPageRendered: false,
        pages: 0, lastError: null, attached: false
    };
    const emit = (event, details = {}) => {
        console.info('FREEPDF_DIAGNOSTIC:' + JSON.stringify({event, ...details}));
    };
    const fail = (event, message, details = {}) => {
        state.lastError = String(message);
        emit(event, {message: String(message), ...details});
    };
    window.addEventListener('error', e => {
        const resource = e.target && (e.target.src || e.target.href);
        if (resource) fail('resource_error', 'Failed to load resource', {resource});
        else fail('javascript_error', e.message || 'Unknown JavaScript error', {
            source: e.filename, line: e.lineno, stack: String(e.error?.stack || '')
        });
    }, true);
    window.addEventListener('unhandledrejection', e => {
        fail('unhandled_rejection', e.reason?.message || String(e.reason), {
            stack: String(e.reason?.stack || '')
        });
    });
    let attempts = 0;
    const attach = () => {
        const app = window.PDFViewerApplication;
        if (!app?.eventBus) {
            if (++attempts < 400) setTimeout(attach, 50);
            else emit('initialization_timeout', {state});
            return;
        }
        state.attached = true;
        state.stage = 'viewer_initialized';
        emit('viewer_initialized', {
            userAgent: navigator.userAgent, version: window.pdfjsLib?.version,
            promiseWithResolvers: typeof Promise.withResolvers,
            urlParse: typeof URL.parse
        });
        const documentLoaded = () => {
            state.documentLoaded = true;
            state.pages = app.pdfDocument?.numPages || app.pagesCount || 0;
            state.stage = 'document_loaded';
            emit('document_loaded', {pages: state.pages});
        };
        app.eventBus.on('documentloaded', documentLoaded);
        app.eventBus.on('pagesinit', () => {
            documentLoaded();
            emit('pages_initialized', {pages: state.pages});
        });
        app.eventBus.on('pagerendered', e => {
            if (e.error) {
                fail('page_render_error', e.error.message || String(e.error), {page: e.pageNumber});
            } else if (!state.firstPageRendered && !e.cssTransform) {
                state.firstPageRendered = true;
                state.stage = 'page_rendered';
                emit('first_page_rendered', {page: e.pageNumber});
            }
        });
        app.eventBus.on('documenterror', e => fail('document_error', e.message || 'PDF load failed'));
        if (app.pdfDocument) documentLoaded();
        // Catch a render completed before the event bus was attached.
        for (let i = 0; i < (app.pdfViewer?.pagesCount || 0); i++) {
            const page = app.pdfViewer.getPageView(i);
            if (page?.renderingState === 3 && page.canvas) {
                state.firstPageRendered = true;
                state.stage = 'page_rendered';
                emit('first_page_rendered', {page: i + 1, recovered: true});
                break;
            }
        }
    };
    emit('document_created');
    attach();
})();
"""

PDFJS_SNAPSHOT_JS = r"""(() => {
    const app = window.PDFViewerApplication;
    const container = document.getElementById('viewerContainer');
    const canvas = document.querySelector('.page canvas');
    return {
        diagnostics: window.__freepdfDiagnostics || null,
        initialized: !!app?.initialized,
        documentLoaded: !!app?.pdfDocument,
        pages: app?.pdfDocument?.numPages || 0,
        pageNumber: app?.pdfViewer?.currentPageNumber || 0,
        viewport: container ? {width: container.clientWidth, height: container.clientHeight} : null,
        canvas: canvas ? {width: canvas.width, height: canvas.height} : null,
        documentVisibility: document.visibilityState,
        userAgent: navigator.userAgent,
        devicePixelRatio: window.devicePixelRatio
    };
})();
"""
