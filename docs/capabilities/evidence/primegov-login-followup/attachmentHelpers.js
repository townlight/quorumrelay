// Avoid the ?? operator here: these files are bundled through ScriptBundle, and the
// AjaxMin minifier (WebGrease 1.6) predates ES2020 and throws NullReferenceException
// when it parses ??, which surfaces as an error on @Scripts.Render for the whole bundle.
function escapeHtmlAttribute(value) {
    return String(value === null || value === undefined ? '' : value)
        .replace(/&/g, '&amp;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;')
        .replace(/</g, '&lt;');
}

function escapeJsString(value) {
    return String(value === null || value === undefined ? '' : value)
        .replace(/\\/g, '\\\\')
        .replace(/'/g, "\\'")
        .replace(/\r/g, '\\r')
        .replace(/\n/g, '\\n')
        .replace(/</g, '\\x3c');
}
