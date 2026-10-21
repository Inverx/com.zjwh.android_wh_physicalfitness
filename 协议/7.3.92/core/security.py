"""HTTPS requests that never forward credentials to a different origin."""
import urllib.error
import urllib.parse
import urllib.request


def https_origin(url):
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme.lower() != "https" or not parsed.hostname
            or parsed.username is not None or parsed.password is not None):
        raise ValueError("Only HTTPS URLs without userinfo are allowed")
    return parsed.hostname.lower(), parsed.port or 443


class SameOriginRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if https_origin(req.full_url) != https_origin(newurl):
            raise urllib.error.HTTPError(req.full_url, code,
                                         "Cross-origin redirect blocked", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def open_https(req, *, context, timeout):
    https_origin(req.full_url)
    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=context), SameOriginRedirectHandler())
    return opener.open(req, timeout=timeout)
