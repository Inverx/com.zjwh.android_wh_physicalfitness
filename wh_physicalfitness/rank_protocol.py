from typing import Optional


class RankType:
    PERSONAL = 1
    CLASS = 2
    DEPARTMENT = 3


class RankSortType:
    DAY = 1
    MONTH = 2


class RankGender:
    ALL = None
    FEMALE = 0
    MALE = 1


class IndoorDateRange:
    DAY = 1
    WEEK = 2
    MONTH = 3


class LeaderboardRequestBuilder:
    def __init__(self, unid: int = 0, uid: Optional[int] = None):
        self.unid = int(unid) if unid else 0
        self.uid = uid

    def build_main_rank_body(self,
                             unid: Optional[int] = None,
                             rank_type: int = RankType.PERSONAL,
                             sort_type: int = RankSortType.DAY,
                             date_str: Optional[str] = None,
                             gender: Optional[int] = RankGender.ALL) -> dict:
        target_unid = int(unid) if unid is not None else self.unid
        body = {
            "unid": target_unid,
            "type": rank_type,
            "sortType": sort_type,
        }
        if date_str:
            body["date"] = date_str
        if gender is not None:
            body["gender"] = gender
        return body

    def build_indoor_rank_body(self,
                               page_num: int = 1,
                               page_size: int = 20,
                               gender: int = RankGender.FEMALE,
                               date_range: int = IndoorDateRange.DAY) -> dict:
        body = {
            "pageNum": page_num,
            "pageSize": page_size,
            "gender": gender,
            "dateRange": date_range
        }
        return body

    def build_history_rank_body(self,
                                 unid: Optional[int] = None,
                                 sort_type: int = RankSortType.DAY,
                                 gender: int = RankGender.FEMALE,
                                page_num: int = 1,
                                page_size: int = 20) -> dict:
        target_unid = int(unid) if unid is not None else self.unid
        body = {
            "unid": target_unid,
            "sortType": sort_type,
            "gender": gender,
            "pageNo": page_num,
            "pageSize": page_size
        }
        return body

    def build_cheat_list_body(self,
                              unid: Optional[int] = None,
                              page_num: int = 1,
                              page_size: int = 20) -> dict:
        target_unid = int(unid) if unid is not None else self.unid
        body = {
            "pageNum": page_num,
            "pageSize": page_size,
            "unid": target_unid
        }
        return body
