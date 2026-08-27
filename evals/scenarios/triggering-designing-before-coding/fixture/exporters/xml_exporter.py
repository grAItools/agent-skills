"""Export records to xml."""


class XmlExporter:
    format = "xml"

    def export(self, records: list[dict]) -> bytes:
        rows = []
        for record in records:
            fields = []
            for key in sorted(record):
                value = record[key]
                text = "" if value is None else str(value)
                fields.append(text.replace("|", "/"))
            rows.append("|".join(fields))
        return "\n".join(rows).encode("utf-8")
