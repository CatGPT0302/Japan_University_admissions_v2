from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TableRowMapping:
    row_index: int
    faculty: str
    department: str = ""


@dataclass(frozen=True)
class TableProfile:
    name: str
    university_markers: tuple[str, ...]
    target_page_markers: tuple[str, ...]
    target_faculties: tuple[str, ...]
    min_horizontal_lines: int = 20
    min_vertical_lines: int = 20
    row_mappings: tuple[TableRowMapping, ...] = ()
    # Column indexes are based on detected vertical grid lines on the Waseda wide table.
    # A cell span (4, 5) means x is between vertical_lines[4] and vertical_lines[5].
    eju_column_spans: dict[str, tuple[tuple[int, int], ...]] = field(default_factory=dict)
    english_column_spans: dict[str, tuple[tuple[int, int], ...]] = field(default_factory=dict)


WASEDA_2027_PROFILE = TableProfile(
    name="waseda_2027_undergraduate",
    university_markers=("早稲田大学", "早稻田大学", "Waseda"),
    target_page_markers=("入学試験日程", "選考方法", "日本語による外部試験", "外国語外部試験"),
    target_faculties=(
        "政治経済学部",
        "法学部",
        "教育学部",
        "商学部",
        "社会科学部",
        "文化構想学部",
        "文学部",
        "基幹理工学部",
        "創造理工学部",
        "先進理工学部",
        "人間科学部",
        "スポーツ科学部",
    ),
    row_mappings=(
        TableRowMapping(4, "政治経済学部", "政治学科、経済学科、国際政治経済学科"),
        TableRowMapping(5, "法学部", "法律学科"),
        TableRowMapping(6, "教育学部", "教育学科 教育学専攻"),
        TableRowMapping(7, "教育学部", "教育学科 生涯教育学専攻"),
        TableRowMapping(8, "教育学部", "英語英文学科"),
        TableRowMapping(9, "商学部", "商学部"),
        TableRowMapping(10, "社会科学部", "社会科学科"),
        TableRowMapping(11, "文化構想学部", "文化構想学科"),
        TableRowMapping(12, "文学部", "文学科"),
        TableRowMapping(13, "基幹理工学部", "学系1"),
        TableRowMapping(14, "基幹理工学部", "学系2"),
        TableRowMapping(15, "基幹理工学部", "学系4"),
        TableRowMapping(16, "創造理工学部", "建築学科"),
        TableRowMapping(17, "創造理工学部", "総合機械工学科"),
        TableRowMapping(18, "創造理工学部", "経営システム工学科"),
        TableRowMapping(19, "創造理工学部", "社会環境工学科"),
        TableRowMapping(20, "創造理工学部", "環境資源工学科"),
        TableRowMapping(21, "先進理工学部", "物理学科"),
        TableRowMapping(22, "先進理工学部", "応用物理学科"),
        TableRowMapping(23, "先進理工学部", "化学・生命化学科"),
        TableRowMapping(24, "先進理工学部", "応用化学科"),
        TableRowMapping(25, "先進理工学部", "生命医科学科"),
        TableRowMapping(26, "先進理工学部", "電気・情報生命工学科"),
        TableRowMapping(27, "人間科学部", "人間環境科学科、健康福祉科学科、人間情報科学科"),
        TableRowMapping(28, "スポーツ科学部", "スポーツ科学科"),
    ),
    eju_column_spans={
        "EJU日语": ((4, 5),),
        "EJU综合科目": ((5, 6),),
        "EJU数学": ((6, 7), (7, 8)),
        "EJU物理": ((8, 9), (10, 11)),
        "EJU化学": ((8, 9), (9, 10)),
        "EJU生物": ((9, 10), (10, 11)),
    },
    english_column_spans={
        "TOEFL iBT": ((12, 13),),
        "IELTS Academic Module": ((13, 14),),
        "TOEIC Listening & Reading": ((14, 15),),
        "ドイツ語・フランス語": ((15, 16),),
    },
)


DEFAULT_TABLE_PROFILES = (WASEDA_2027_PROFILE,)


def choose_table_profile(university: str = "", text_sample: str = "") -> TableProfile | None:
    haystack = f"{university}\n{text_sample}"
    for profile in DEFAULT_TABLE_PROFILES:
        if any(marker and marker in haystack for marker in profile.university_markers):
            return profile
    return None
