import bleach
from django.utils.deprecation import MiddlewareMixin

# Aturan sanitasi
ALLOWED_TAGS = [
    'p', 'br', 'strong', 'b', 'em', 'i', 'u',
    'ul', 'ol', 'li',
    'blockquote',
    'h1', 'h2', 'h3', 'pre', 'code',
]

ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title', 'rel', 'target'],
}

ALLOWED_PROTOCOLS = ['http', 'https', 'mailto']

def sanitize_html(value: str) -> str:
    cleaned = bleach.clean(
        value or '',
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=True
    )

    # Tambahan keamanan untuk <a>
    def set_link_attrs(attrs, new=False):
        href = attrs.get('href', '')
        if href and not any(href.startswith(proto + ':') for proto in ALLOWED_PROTOCOLS):
            attrs.pop('href', None)
            return attrs
        attrs['rel'] = 'nofollow noopener noreferrer'
        attrs['target'] = '_blank'
        return attrs

    return bleach.linkify(
        cleaned,
        callbacks=[lambda attrs, new: set_link_attrs(attrs, new)]
    )

class SanitizeHTMLMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if request.method == 'POST' and 'content' in request.POST:
            # Membuat request.POST menjadi writable
            _mutable = request.POST._mutable
            request.POST._mutable = True
            request.POST['content'] = sanitize_html(request.POST['content'])
            request.POST._mutable = _mutable