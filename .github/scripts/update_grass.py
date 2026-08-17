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

BASE_POINT = 10

# 연속 풀이 1일 증가마다 다음 풀이에서 +2점
STREAK_BONUS_PER_DAY = 2

# 스트릭 보너스 최대 +20점
MAX_STREAK_BONUS = 20


# =========================================================
# 잔디 색상
# =========================================================

EMPTY = "#ebedf0"
SOLVED = "#216e39"


# =========================================================
# 배지 색상
# =========================================================

BADGE_COLORS = {
    "UNRANKED": "#6e7781",
    "BRONZE": "#bc6f3c",
    "SILVER": "#8c959f",
    "GOLD": "#bf8700",
    "PLATINUM": "#8250df",
    "DIAMOND": "#1f6feb",
}


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
# 확장자 → 언어
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
    return (
        text
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .strip()
    )


# =========================================================
# README 멤버 추출
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
            "README에서 스터디 멤버를 찾지 못했습니다."
        )

    return result


# =========================================================
# 날짜
# =========================================================

def today_kst() -> date:
    return datetime.now(
        ZoneInfo("Asia/Seoul")
    ).date()


def actual_date(
    folder: str,
) -> date:

    month, day = map(
        int,
        folder.split("-"),
    )

    today = today_kst()

    candidate = date(
        today.year,
        month,
        day,
    )

    # 연말 → 연초 대응
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

    - 날짜 형식
    - 평일
    - 실제 문제 폴더 존재

    조건을 만족하는 날짜만 가져온다.
    """

    days = []

    if not PROBLEM_ROOT.exists():
        return []

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

        # 토요일 / 일요일 제외
        if current_date.weekday() >= 5:
            continue

        # 실제 문제 폴더가 있는 날짜만 사용
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
# 제출 여부
# =========================================================

def submitted_file(
    path: Path,
    username: str,
) -> bool:

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

    # 자동 생성 대상이 아닌 확장자라면
    # 내용이 있는 경우 제출로 판단
    if language is None:
        return bool(
            normalize(content)
        )

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
    평일 하루 1문제 기준.

    해당 날짜 문제 폴더에서 자기 파일이
    자동 생성 템플릿과 다르면 풀이 완료.
    """

    for problem in day.iterdir():

        if not problem.is_dir():
            continue

        for file in problem.iterdir():

            if not file.is_file():
                continue

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
# 배지
# =========================================================

def badge_name(
    score: int,
) -> str:

    if score >= 800:
        return "DIAMOND"

    if score >= 500:
        return "PLATINUM"

    if score >= 250:
        return "GOLD"

    if score >= 100:
        return "SILVER"

    if score > 0:
        return "BRONZE"

    return "UNRANKED"


# =========================================================
# 점수 / 스트릭
# =========================================================

def calculate(
    members: list[dict[str, str]],
    days: list[Path],
) -> dict:

    result = {}

    today = today_kst()

    current_year = today.year
    current_month = today.month

    for member in members:

        username = member[
            "username"
        ]

        solved_list = []

        # -----------------------------------------
        # 전체 누적 점수 계산용
        # -----------------------------------------

        score = 0
        streak = 0

        # -----------------------------------------
        # 이번 달 통계
        # -----------------------------------------

        month_streak = 0
        month_longest = 0
        month_participation = 0

        for day in days:

            done = solved_on_day(
                day,
                username,
            )

            solved_list.append(
                done
            )

            # =====================================
            # 전체 누적 점수
            # =====================================

            if done:

                streak += 1

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

            else:

                streak = 0

            # =====================================
            # 이번 달 통계
            # =====================================

            day_date = actual_date(
                day.name
            )

            if not (
                day_date.year
                == current_year
                and day_date.month
                == current_month
            ):
                continue

            if done:

                month_participation += 1

                month_streak += 1

                month_longest = max(
                    month_longest,
                    month_streak,
                )

            else:

                month_streak = 0

        result[
            username
        ] = {
            "solved": solved_list,

            # 전체 누적
            "score": score,
            "badge": badge_name(
                score
            ),

            # 이번 달
            "month_participation": (
                month_participation
            ),
            "month_longest": (
                month_longest
            ),
        }

    return result


# =========================================================
# SVG
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

    # =====================================================
    # Layout
    # =====================================================

    cell = 14
    gap = 4

    step = (
        cell
        + gap
    )

    # -----------------------------------------------------
    # 왼쪽
    #
    # 이름 / 점수 / 배지를 잔디와 같은 행에 배치하기 위해
    # 기존보다 넓게 잡음
    # -----------------------------------------------------

    left = 270

    # -----------------------------------------------------
    # 날짜 라벨 공간
    #
    # 기존 72px → 120px
    #
    # 08-17 같은 날짜가 회전되었을 때
    # SVG 위쪽에서 잘리지 않도록 충분히 확보
    # -----------------------------------------------------

    top = 120

    row_height = 28

    # 오른쪽 이번달 통계 영역
    right = 255

    grass_width = (
        len(days)
        * step
    )

    width = max(
        750,
        left
        + grass_width
        + right,
    )

    height = (
        top
        + len(members)
        * row_height
        + 25
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
            f'viewBox="0 0 {width} {height}" '
            f'role="img">'
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
            "font-weight:700"
            "}"
        ),

        (
            ".score{"
            "font-size:11px;"
            "font-weight:600;"
            "fill:#57606a"
            "}"
        ),

        (
            ".badge{"
            "font-size:9px;"
            "font-weight:700;"
            "fill:#ffffff"
            "}"
        ),

        (
            ".date{"
            "font-size:10px;"
            "fill:#57606a"
            "}"
        ),

        (
            ".month-stat{"
            "font-size:11px;"
            "fill:#57606a"
            "}"
        ),

        (
            "@media(prefers-color-scheme:dark){"
            "text{fill:#c9d1d9}"
            ".date,"
            ".score,"
            ".month-stat{fill:#8b949e}"
            "}"
        ),

        "</style>",
    ]

    # =====================================================
    # 날짜 라벨
    # =====================================================

    for column, day in enumerate(
        days
    ):

        x = (
            left
            + column * step
            + cell / 2
        )

        # 날짜 셀보다 위에 배치
        y = (
            top - 20
        )

        # -------------------------------------------------
        # text-anchor=start로 두고 -45도 회전
        # 위쪽 공간을 충분히 확보했기 때문에 잘리지 않음
        # -------------------------------------------------

        output.append(
            (
                f'<text '
                f'x="{x:.1f}" '
                f'y="{y}" '
                f'class="date" '
                f'text-anchor="start" '
                f'transform="'
                f'rotate(-45 {x:.1f} {y})'
                f'">'
                f'{escape(day.name)}'
                f'</text>'
            )
        )

    # =====================================================
    # 멤버
    # =====================================================

    for row, member in enumerate(
        members
    ):

        username = member[
            "username"
        ]

        member_stats = stats[
            username
        ]

        score = member_stats[
            "score"
        ]

        badge = member_stats[
            "badge"
        ]

        badge_color = BADGE_COLORS[
            badge
        ]

        y = (
            top
            + row * row_height
        )

        # =================================================
        # 이름
        # =================================================

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

        # =================================================
        # 참여 점수
        # =================================================

        output.append(
            (
                f'<text '
                f'x="72" '
                f'y="{y + 11}" '
                f'class="score">'
                f'{score}점'
                f'</text>'
            )
        )

        # =================================================
        # 배지
        # =================================================

        badge_x = 125
        badge_y = y - 1

        badge_width = 88
        badge_height = 17

        output.append(
            (
                f'<rect '
                f'x="{badge_x}" '
                f'y="{badge_y}" '
                f'width="{badge_width}" '
                f'height="{badge_height}" '
                f'rx="8.5" '
                f'fill="{badge_color}"'
                f'/>'
            )
        )

        output.append(
            (
                f'<text '
                f'x="{badge_x + badge_width / 2}" '
                f'y="{badge_y + 11.5}" '
                f'class="badge" '
                f'text-anchor="middle">'
                f'{badge}'
                f'</text>'
            )
        )

        # =================================================
        # 날짜별 잔디
        # =================================================

        for column, done in enumerate(
            member_stats["solved"]
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
                    ),

                    (
                        f'<title>'
                        f'{escape(title)}'
                        f'</title>'
                    ),

                    "</rect>",

                    "</a>",
                ]
            )

        # =================================================
        # 이번달 참여 / 최장 스트릭
        # =================================================

        stat_x = (
            left
            + grass_width
            + 18
        )

        month_participation = (
            member_stats[
                "month_participation"
            ]
        )

        month_longest = (
            member_stats[
                "month_longest"
            ]
        )

        output.append(
            (
                f'<text '
                f'x="{stat_x}" '
                f'y="{y + 11}" '
                f'class="month-stat">'
                f'이번달 참여 '
                f'{month_participation}회'
                f' · '
                f'최장 스트릭 '
                f'{month_longest}일'
                f'</text>'
            )
        )

    output.append(
        "</svg>"
    )

    return "\n".join(
        output
    )


# =========================================================
# README 블록
# =========================================================

def activity_block() -> str:

    return "\n".join(
        [
            START,

            "## 🌱 알고리즘 잔디",

            "",

            (
                "> 평일 **1일 1문제** 기준입니다. "
                "초록색은 풀이 완료, 회색은 미제출입니다."
            ),

            "",

            (
                "[![Algorithm Grass]"
                "(./assets/algorithm-grass.svg)]"
                "(./problem_solve)"
            ),

            "",

            (
                "> **점수:** 첫 풀이 10점 · "
                "연속 풀이 시 다음 문제부터 +2점 · "
                "스트릭 보너스 최대 +20점"
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

            END,
        ]
    )


def update_readme(
    text: str,
    block: str,
) -> str:

    # 기존 영역 갱신
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

    # 최초 생성
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

    readme = README.read_text(
        encoding="utf-8"
    )

    members = members_from_readme(
        readme
    )

    days = study_days()

    stats = calculate(
        members,
        days,
    )

    # =====================================================
    # SVG
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
    # README
    # =====================================================

    README.write_text(
        update_readme(
            readme,
            activity_block(),
        ),
        encoding="utf-8",
    )

    # =====================================================
    # 로그
    # =====================================================

    print(
        f"집계 완료: "
        f"{len(members)}명 / "
        f"{len(days)}회"
    )

    for member in members:

        stat = stats[
            member["username"]
        ]

        print(
            f'- {member["name"]}: '
            f'{stat["score"]}점 / '
            f'{stat["badge"]} / '
            f'이번달 참여 '
            f'{stat["month_participation"]}회 / '
            f'이번달 최장 스트릭 '
            f'{stat["month_longest"]}일'
        )


if __name__ == "__main__":
    main()
