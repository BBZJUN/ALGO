from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo
import html
import os
import re

from generate_daily import build_code_template


README = Path("README.md")
PROBLEM_ROOT = Path("problem_solve")
GRASS_SVG = Path("assets/algorithm-grass.svg")

START = "<!-- ALGORITHM_ACTIVITY:START -->"
END = "<!-- ALGORITHM_ACTIVITY:END -->"

# =========================================================
# 점수 정책
# =========================================================

# 문제를 풀었을 때 기본 점수
BASE_POINT = 10

# 스트릭 1일 증가마다 추가되는 점수
STREAK_BONUS_PER_DAY = 2

# 스트릭으로 받을 수 있는 최대 추가 점수
MAX_STREAK_BONUS = 20


# =========================================================
# 잔디 색상
# =========================================================

EMPTY = "#ebedf0"
SOLVED = "#216e39"


# =========================================================
# 패턴
# =========================================================

DATE_RE = re.compile(
    r"^\d{2}-\d{2}$"
)

MEMBER_RE = re.compile(
    r'<a\s+href=["\']https://github\.com/'
    r'(?P<username>[^/"\'?#]+)["\'][^>]*>'
    r'\s*<b>(?P<name>.*?)</b>\s*</a>',
    re.I | re.S,
)


# =========================================================
# 확장자 → generate_daily.py 언어 이름
# =========================================================

EXT_TO_LANG = {
    ".java": "java",
    ".swift": "swift",
    ".py": "python",
    ".cpp": "c++",
    ".cc": "c++",
    ".cxx": "c++",
    ".c": "c",
    ".kt": "kotlin",
    ".js": "javascript",
    ".ts": "typescript",
}


def normalize(text: str) -> str:
    """
    개행이나 마지막 공백 차이 때문에
    제출로 잘못 판단하지 않도록 정규화한다.
    """

    return (
        text
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .strip()
    )


# =========================================================
# README에서 스터디 멤버 읽기
# =========================================================

def members_from_readme(
    text: str,
) -> list[dict[str, str]]:

    result = []
    seen = set()

    for match in MEMBER_RE.finditer(text):

        username = html.unescape(
            match.group("username")
        ).strip()

        name = re.sub(
            r"<[^>]+>",
            "",
            match.group("name"),
        )

        name = (
            html.unescape(name).strip()
            or username
        )

        key = username.lower()

        if key in seen:
            continue

        seen.add(key)

        result.append(
            {
                "username": username,
                "name": name,
            }
        )

    if not result:
        raise ValueError(
            "README의 스터디 멤버 표를 "
            "찾지 못했습니다."
        )

    return result


# =========================================================
# 날짜 처리
# =========================================================

def actual_date(
    folder: str,
) -> date:

    month, day = map(
        int,
        folder.split("-"),
    )

    today = datetime.now(
        ZoneInfo("Asia/Seoul")
    ).date()

    candidate = date(
        today.year,
        month,
        day,
    )

    # 연초/연말 대응
    if (
        candidate
        > today + timedelta(days=45)
    ):
        candidate = date(
            today.year - 1,
            month,
            day,
        )

    return candidate


def study_days() -> list[Path]:
    """
    problem_solve/MM-DD 중

    1. 실제 날짜 형식이고
    2. 평일이고
    3. 문제 폴더가 존재하는 날짜

    만 스터디 날짜로 사용한다.
    """

    days = []

    for path in PROBLEM_ROOT.iterdir():

        if not path.is_dir():
            continue

        if not DATE_RE.fullmatch(
            path.name
        ):
            continue

        try:
            current_date = actual_date(
                path.name
            )

        except ValueError:
            continue

        # -----------------------------------------
        # 토요일 / 일요일 제외
        # -----------------------------------------

        if current_date.weekday() >= 5:
            continue

        # -----------------------------------------
        # 실제 문제 폴더가 없는 날짜 제외
        # -----------------------------------------

        has_problem = any(
            child.is_dir()
            for child in path.iterdir()
        )

        if not has_problem:
            continue

        days.append(
            (
                current_date,
                path,
            )
        )

    days.sort(
        key=lambda item: item[0]
    )

    return [
        path
        for _, path in days
    ]


# =========================================================
# 제출 여부 판정
# =========================================================

def submitted_file(
    path: Path,
    username: str,
) -> bool:
    """
    현재 파일과 generate_daily.py가 생성하는
    기본 템플릿을 비교한다.

    같음   → 미제출
    다름   → 제출
    """

    try:
        content = path.read_text(
            encoding="utf-8"
        )

    except UnicodeDecodeError:

        return (
            path.stat().st_size > 0
        )

    language = EXT_TO_LANG.get(
        path.suffix.lower()
    )

    # -----------------------------------------
    # generate_daily.py에서 관리하지 않는
    # 확장자라면 내용 존재 여부로 판단
    # -----------------------------------------

    if language is None:

        return bool(
            normalize(content)
        )

    # -----------------------------------------
    # 기존 자동 생성 템플릿 가져오기
    # -----------------------------------------

    template = build_code_template(
        username,
        language,
    )

    return (
        normalize(content)
        != normalize(template)
    )


def solved_on_day(
    day: Path,
    username: str,
) -> bool:
    """
    평일 1일 1문제 기준.

    해당 날짜 문제 폴더에서
    자신의 코드 파일이 기본 템플릿과 다르면
    그날 문제를 푼 것으로 판단한다.
    """

    for problem in day.iterdir():

        if not problem.is_dir():
            continue

        for file in problem.iterdir():

            if not file.is_file():
                continue

            # ---------------------------------
            # GitHub 사용자명과
            # 파일명이 같은 파일만 확인
            # ---------------------------------

            if (
                file.stem.lower()
                != username.lower()
            ):
                continue

            if submitted_file(
                file,
                username,
            ):
                return True

    return False


# =========================================================
# 점수 / 스트릭 계산
# =========================================================

def calculate(
    members: list[dict[str, str]],
    days: list[Path],
) -> dict:

    result = {}

    for member in members:

        username = member[
            "username"
        ]

        solved = []

        score = 0
        streak = 0
        longest = 0

        for day in days:

            done = solved_on_day(
                day,
                username,
            )

            solved.append(
                done
            )

            # ---------------------------------
            # 미제출
            # → 스트릭 초기화
            # ---------------------------------

            if not done:

                streak = 0

                continue

            # ---------------------------------
            # 제출
            # ---------------------------------

            streak += 1

            longest = max(
                longest,
                streak,
            )

            # ---------------------------------
            # 스트릭 보너스
            #
            # 1일차 0
            # 2일차 +2
            # 3일차 +4
            # ...
            # 최대 +20
            # ---------------------------------

            bonus = min(
                (
                    streak - 1
                )
                * STREAK_BONUS_PER_DAY,

                MAX_STREAK_BONUS,
            )

            score += (
                BASE_POINT
                + bonus
            )

        result[
            username
        ] = {
            "solved": solved,
            "score": score,
            "longest": longest,
        }

    return result


# =========================================================
# 배지 정책
# =========================================================

def badge(
    score: int,
) -> tuple[str, str, str]:

    if score >= 800:

        return (
            "DIAMOND",
            "1f6feb",
            "800%2B",
        )

    if score >= 500:

        return (
            "PLATINUM",
            "8250df",
            "500%2B",
        )

    if score >= 250:

        return (
            "GOLD",
            "d4a72c",
            "250%2B",
        )

    if score >= 100:

        return (
            "SILVER",
            "8c959f",
            "100%2B",
        )

    if score > 0:

        return (
            "BRONZE",
            "bc6f3c",
            "1%2B",
        )

    return (
        "UNRANKED",
        "6e7781",
        "0",
    )


def badge_md(
    score: int,
) -> str:

    name, color, threshold = (
        badge(score)
    )

    return (
        f"![{name}]"
        f"(https://img.shields.io/badge/"
        f"{name}-{threshold}-{color}"
        f"?style=flat-square)"
    )


# =========================================================
# SVG 생성
# =========================================================

def escape(
    value: str,
) -> str:

    return html.escape(
        value,
        quote=True,
    )


def make_svg(
    members: list[dict[str, str]],
    days: list[Path],
    stats: dict,
) -> str:
    """
    README에 표시할 잔디 SVG.

    행에는:
    이름 + 잔디

    만 표시한다.
    """

    cell = 14
    gap = 4

    step = (
        cell
        + gap
    )

    left = 125
    top = 72
    row_height = 25

    width = max(
        360,

        left
        + len(days) * step
        + 12,
    )

    height = (
        top
        + len(members)
        * row_height
        + 22
    )

    repository = os.getenv(
        "GITHUB_REPOSITORY",
        "Chwippo-Eleven/ALGO",
    )

    output = [

        (
            f'<svg '
            f'xmlns="http://www.w3.org/2000/svg" '
            f'xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'width="{width}" '
            f'height="{height}" '
            f'viewBox="0 0 {width} {height}">'
        ),

        "<style>",

        (
            "text{"
            "font-family:"
            "-apple-system,"
            "BlinkMacSystemFont,"
            "'Segoe UI',"
            "Helvetica,"
            "Arial,"
            "sans-serif;"
            "fill:#24292f"
            "}"
        ),

        (
            ".name{"
            "font-size:12px;"
            "font-weight:600"
            "}"
        ),

        (
            ".date{"
            "font-size:10px;"
            "fill:#57606a"
            "}"
        ),

        (
            "@media(prefers-color-scheme:dark){"
            "text{fill:#c9d1d9}"
            ".date{fill:#8b949e}"
            "}"
        ),

        "</style>",
    ]

    # =====================================================
    # 날짜
    # =====================================================

    for column, day in enumerate(
        days
    ):

        x = (
            left
            + column * step
            + cell / 2
        )

        y = (
            top - 10
        )

        output.append(
            (
                f'<text '
                f'x="{x:.1f}" '
                f'y="{y}" '
                f'class="date" '
                f'text-anchor="end" '
                f'transform="'
                f'rotate(-45 {x:.1f} {y})'
                f'">'
                f'{escape(day.name)}'
                f'</text>'
            )
        )

    # =====================================================
    # 멤버별 잔디
    # =====================================================

    for row, member in enumerate(
        members
    ):

        username = member[
            "username"
        ]

        y = (
            top
            + row * row_height
        )

        # -----------------------------------------
        # 이름만 표시
        # -----------------------------------------

        output.append(
            (
                f'<text '
                f'x="0" '
                f'y="{y + 11}" '
                f'class="name">'
                f'{escape(member["name"])}'
                f'</text>'
            )
        )

        # -----------------------------------------
        # 날짜별 잔디
        # -----------------------------------------

        for column, done in enumerate(
            stats[username]["solved"]
        ):

            day = days[
                column
            ]

            x = (
                left
                + column * step
            )

            color = (
                SOLVED
                if done
                else EMPTY
            )

            url = (
                f"https://github.com/"
                f"{repository}/tree/main/"
                f"problem_solve/"
                f"{quote(day.name, safe='')}"
            )

            status = (
                "풀이 완료"
                if done
                else "미제출"
            )

            title = (
                f'{member["name"]} · '
                f'{day.name} · '
                f'{status}'
            )

            output.extend(
                [
                    (
                        f'<a '
                        f'xlink:href="'
                        f'{escape(url)}" '
                        f'target="_blank">'
                    ),

                    (
                        f'<rect '
                        f'x="{x}" '
                        f'y="{y}" '
                        f'width="{cell}" '
                        f'height="{cell}" '
                        f'rx="3" '
                        f'fill="{color}">'
                        f'<title>'
                        f'{escape(title)}'
                        f'</title>'
                        f'</rect>'
                    ),

                    "</a>",
                ]
            )

    output.append(
        "</svg>"
    )

    return "\n".join(
        output
    )


# =========================================================
# 참여 점수 표
# =========================================================

def score_table(
    members: list[dict[str, str]],
    stats: dict,
) -> str:

    lines = [
        "## 🏅 참여 점수",
        "",
        "| 이름 | 점수 | 최장 스트릭 | 배지 |",
        "|:---|---:|---:|:---:|",
    ]

    for member in members:

        member_stats = stats[
            member["username"]
        ]

        score = member_stats[
            "score"
        ]

        longest = member_stats[
            "longest"
        ]

        lines.append(
            (
                f'| {member["name"]} '
                f'| **{score}점** '
                f'| **{longest}일** '
                f'| {badge_md(score)} |'
            )
        )

    lines.extend(
        [
            "",
            (
                f"> **점수 규칙:** "
                f"첫 풀이 {BASE_POINT}점, "
                f"연속 풀이가 이어질 때마다 "
                f"다음 풀이에 "
                f"+{STREAK_BONUS_PER_DAY}점. "
                f"스트릭 보너스는 "
                f"최대 +{MAX_STREAK_BONUS}점으로 "
                f"하루 최대 "
                f"{BASE_POINT + MAX_STREAK_BONUS}점입니다."
            ),
            "",
            (
                "> 문제를 놓친 스터디 날짜가 있으면 "
                "스트릭은 초기화됩니다. "
                "토·일과 문제 폴더가 없는 날은 "
                "스트릭을 끊지 않습니다."
            ),
            "",
            (
                "> **배지:** "
                "BRONZE 1+ · "
                "SILVER 100+ · "
                "GOLD 250+ · "
                "PLATINUM 500+ · "
                "DIAMOND 800+"
            ),
        ]
    )

    return "\n".join(
        lines
    )


# =========================================================
# README 자동 블록
# =========================================================

def activity_block(
    members: list[dict[str, str]],
    stats: dict,
) -> str:

    return "\n".join(
        [
            START,

            "## 🌱 알고리즘 잔디",

            "",

            (
                "> 평일 **1일 1문제** 기준입니다. "
                "초록색이면 해당 날짜 문제 풀이 완료입니다."
            ),

            "",

            (
                "[![Algorithm Grass]"
                "(./assets/algorithm-grass.svg)]"
                "(./problem_solve)"
            ),

            "",

            score_table(
                members,
                stats,
            ),

            END,
        ]
    )


def update_readme(
    text: str,
    block: str,
) -> str:

    # =====================================================
    # 기존 블록이 있다면 교체
    # =====================================================

    if (
        START in text
        and END in text
    ):

        pattern = re.compile(
            re.escape(START)
            + r".*?"
            + re.escape(END),

            re.S,
        )

        return pattern.sub(
            lambda _: block,
            text,
        )

    # =====================================================
    # 처음 생성하는 경우
    # 데일리 문제 영역 앞에 삽입
    # =====================================================

    heading = re.search(
        r"^###\s*🟨",
        text,
        re.M,
    )

    if heading:

        index = heading.start()

        return (
            text[:index].rstrip()
            + "\n\n<br />\n\n"
            + block
            + "\n\n<br />\n\n"
            + text[index:].lstrip()
        )

    # =====================================================
    # 데일리 영역을 찾지 못하면 맨 아래 삽입
    # =====================================================

    return (
        text.rstrip()
        + "\n\n"
        + block
        + "\n"
    )


# =========================================================
# 실행
# =========================================================

def main() -> None:

    if not README.exists():

        raise FileNotFoundError(
            "README.md가 없습니다."
        )

    if not PROBLEM_ROOT.exists():

        raise FileNotFoundError(
            "problem_solve 폴더가 없습니다."
        )

    # =====================================================
    # README
    # =====================================================

    readme = README.read_text(
        encoding="utf-8"
    )

    members = members_from_readme(
        readme
    )

    # =====================================================
    # 기존 날짜 전체 수집
    # =====================================================

    days = study_days()

    # =====================================================
    # 과거 포함 전체 점수 계산
    # =====================================================

    stats = calculate(
        members,
        days,
    )

    # =====================================================
    # SVG 생성
    # =====================================================

    GRASS_SVG.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    GRASS_SVG.write_text(
        make_svg(
            members,
            days,
            stats,
        )
        + "\n",

        encoding="utf-8",
    )

    # =====================================================
    # README 갱신
    # =====================================================

    README.write_text(
        update_readme(
            readme,

            activity_block(
                members,
                stats,
            ),
        ),

        encoding="utf-8",
    )

    # =====================================================
    # Action 로그
    # =====================================================

    print(
        f"집계 완료: "
        f"{len(members)}명 / "
        f"{len(days)}회"
    )

    for member in members:

        member_stats = stats[
            member["username"]
        ]

        print(
            f'- {member["name"]}: '
            f'{member_stats["score"]}점 / '
            f'최장 '
            f'{member_stats["longest"]}일'
        )


if __name__ == "__main__":
    main()
