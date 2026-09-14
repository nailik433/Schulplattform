"""Local QR-code generation (no external service, so student tokens never
leave the server)."""

import io

import qrcode
from django.utils.safestring import mark_safe
from qrcode.image.svg import SvgPathImage


def qr_svg(data, box_size=10, border=1):
    """Return inline SVG markup encoding ``data`` (safe to embed in a page).

    The SVG scales to its container, so the size is controlled purely by CSS
    on the wrapping element.
    """
    img = qrcode.make(
        data, image_factory=SvgPathImage, box_size=box_size, border=border
    )
    buf = io.BytesIO()
    img.save(buf)
    svg = buf.getvalue().decode("utf-8")

    # Drop the XML declaration so the SVG can be inlined in HTML.
    if svg.startswith("<?xml"):
        svg = svg.split("?>", 1)[1].lstrip()

    # Let the SVG fill its container instead of using the fixed mm size that
    # the library sets, so print CSS can size the cards.
    svg = svg.replace(
        "<svg ", '<svg preserveAspectRatio="xMidYMid meet" ', 1
    )
    return mark_safe(svg)
