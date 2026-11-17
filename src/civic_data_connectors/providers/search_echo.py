"""Validate query controls echoed by captured public HTML search responses."""
from html.parser import HTMLParser


class _Echo(HTMLParser):
    def __init__(self, content, name):
        super().__init__(convert_charrefs=True)
        self.name, self.values, self.hidden = name, [], 0
        self.feed(content.decode("utf-8-sig", errors="strict"))

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "template"}:
            self.hidden += 1
        a = dict(attrs)
        if not self.hidden and tag == "input" and a.get("name") == self.name:
            if len(a) != len(attrs) or a.get("type", "text").lower() != "text":
                raise ValueError("Ambiguous search response query control.")
            self.values.append(a.get("value"))

    def handle_endtag(self, tag):
        if tag in {"script", "style", "template"}:
            self.hidden = max(0, self.hidden - 1)


def require_search_echo(content, name, expression):
    if _Echo(content, name).values != [expression]:
        raise ValueError("Search response does not echo the exact requested expression once.")
