from static.dServices import sheetService


def get_sheet_data(spreadsheet_id: str, range_str: str) -> list[list[str]]:
    result = sheetService.get(
        spreadsheetId=spreadsheet_id,
        range=range_str,
    ).execute()
    return result.get("values", [])


def update_sheet_data(
    spreadsheet_id: str,
    range_str: str,
    parse_input: bool,
    data: list[list[str]],
):
    result = sheetService.update(
        spreadsheetId=spreadsheet_id,
        range=range_str,
        valueInputOption="USER_ENTERED" if parse_input else "RAW",
        body={"values": data},
    ).execute()
    print(result)
