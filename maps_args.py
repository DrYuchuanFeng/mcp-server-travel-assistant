"""
Google 地图工具的参数清洗
-------------------------
模型经常把所有可选字段都填满（空字符串、全 0 坐标、编造的日期），
同一地点还会同时传 address / latLng / placeId，Google 接口会直接返回 400。
这里在真正调用工具前把参数规范成接口接受的形式。
"""

from datetime import date, datetime, timezone
from typing import Any

MAPS_TOOLS = {"search_places", "lookup_weather", "compute_routes", "search_along_route", "resolve_names"}

# 同一个对象里只能出现其中一个，按可靠程度排序（模型编造 placeId 和坐标的概率更高）
_LOCATION_KEYS = ("address", "placeId", "latLng")
_ROUTE_SOURCE_KEYS = ("routeEndpoints", "retrievalToken", "encodedPolyline")


def _keep_first(args: dict[str, Any], keys: tuple[str, ...]) -> None:
    present = [key for key in keys if key in args]
    for key in present[1:]:
        del args[key]


def _clean(value: Any) -> Any:
    """递归去掉空值、*_UNSPECIFIED 枚举和全 0 对象，并让地点只保留一种定位方式。"""
    if isinstance(value, list):
        return [item for item in map(_clean, value) if not _is_empty(item)]
    if not isinstance(value, dict):
        return value

    cleaned = {key: _clean(item) for key, item in value.items()}
    cleaned = {key: item for key, item in cleaned.items() if not _is_empty(item)}
    if cleaned and all(item == 0 for item in cleaned.values()):
        return {}
    if "center" in value and "center" not in cleaned:  # 圆形范围没有有效圆心
        return {}
    _keep_first(cleaned, _LOCATION_KEYS)
    return cleaned


def _is_empty(value: Any) -> bool:
    if isinstance(value, str):
        return not value.strip() or value.endswith("_UNSPECIFIED")
    return value is None or value == [] or value == {}


def _is_future(timestamp: str) -> bool:
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        return parsed > datetime.now(timezone.utc)
    except (TypeError, ValueError):  # 格式错误或缺少时区
        return False


def _clean_route_times(args: dict[str, Any]) -> None:
    """到达时间只支持公共交通；两个时间只能给一个；过去的时间会被接口拒绝。"""
    if args.get("travelMode") != "TRANSIT" or "departureTime" in args:
        args.pop("arrivalTime", None)
    for key in ("departureTime", "arrivalTime"):
        if key in args and not _is_future(args[key]):
            del args[key]


def _clean_weather_date(args: dict[str, Any]) -> None:
    """查询日期早于今天时回退为当前天气；小时必须和有效日期一起使用，0 视为模型填的默认值。"""
    day = args.get("date")
    if day is not None:
        try:
            if date(day["year"], day["month"], day["day"]) < date.today():
                del args["date"]
        except (KeyError, TypeError, ValueError):
            del args["date"]
    if "date" not in args or not args.get("hour"):
        args.pop("hour", None)


def sanitize_maps_args(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    """返回清洗后的工具参数。"""
    cleaned = _clean(args)
    if tool_name in ("compute_routes", "search_along_route"):
        cleaned.pop("routingPreference", None)  # 只支持驾车，默认值已足够
    if tool_name == "compute_routes":
        _clean_route_times(cleaned)
    elif tool_name == "search_along_route":
        _keep_first(cleaned, _ROUTE_SOURCE_KEYS)
    elif tool_name == "lookup_weather":
        # 实测这些字段会让接口返回 “The caller does not have permission”，不传时默认查询天气
        for key in ("capabilities", "airQualityOptions", "languageCode", "weatherOptions"):
            cleaned.pop(key, None)
        _clean_weather_date(cleaned)
    return cleaned
