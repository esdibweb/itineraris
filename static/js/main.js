// Returns the CSRF token from the csrftoken cookie, for forms built in JavaScript
function getCSRFToken() {
    const cookie = document.cookie
        .split(';')
        .map((c) => c.trim())
        .find((c) => c.startsWith('csrftoken='));
    return cookie ? cookie.substring('csrftoken='.length) : null;
}
