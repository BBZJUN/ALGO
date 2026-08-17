from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo
import html
import os
import re

# 기존 generate_daily.py가 사용하는 템플릿을 그대로 재사용한다.
from generate_daily import build_code_template


README_PATH = Path("README.md")
PROBLEM_ROOT = Path("problem_solve")
OUTPUT_PATH = Path("assets/algorithm-grass.svg")

# README 잔디에 표시할 최근 데일리 회차 수
MAX_DAYS = 35

DATE_PATTERN = re.compile(r"^\d{2}-\d{2}$")

# README의
# <a href="https://github.com/oneul0"><b>김기훈</b></a>
# 형태에서 사용자명/이름 추출
MEMBER_PATTERN = re.compile(
    r'<a\s+href=["\']https://github\.com/(?P<username>[^/"\'?#]+)["\'][^>]*>'
    r'\s*<b>(?P<name>.*?)</b>\s*</a>',
    re.IGNORECASE | re.DOTALL,
)

EXTENSION_TO_LANGUAGE = {
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

# GitHub Contribution Graph와 비슷한 색상
GRASS_COLORS = {
    0: "#ebedf0",
    1: "#9be9a8",
    2: "#40c463",
    3: "#30a14e",
    4: "#216e39",
}

GRASS_START = "<!-- ALGORITHM_GRASS:START -->"
GRASS_END = "<!-- ALGORITHM_GRASS:END -->"


@dataclass(frozen=True)
class Member:
    username: str
    name: str


@dataclass(frozen=True)
class DailyResult:
    date: str
    solved: int
    total: int

    @property
    def level(self) -> int:
        """
        하루 전체 문제 중 몇 문제를 풀었는지에 따라
        잔디 농도를 0~4단계로 계산한다.
        """

        if self.total == 0 or self.solved == 0:
            return 0

        if self.solved >= self.total:
            return 4

        ratio = self.solved / self.total

        if ratio <= 0.25:
            return 1

        if ratio <= 0.50:
            return 2

        if ratio <= 0.75:
            return 3

        return 4


def normalize(text: str) -> str:
    """
    OS별 개행 차이나 파일 끝 개행 때문에
    제출 여부가 잘못 판정되지 않도록 정규화한다.
    """

    return (
        text
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .strip()
    )


def extract_members(readme: str) -> list[Member]:
    """
    루트 README의 스터디 멤버 표에서

    GitHub username
    실제 이름

    을 가져온다.
    """

    members: list[Member] = []
    seen: set[str] = set()

    for match in MEMBER_PATTERN.finditer(readme):
        username = html.unescape(
            match.group("username")
        ).strip()

        name = re.sub(
            r"<[^>]+>",
            "",
            match.group("name"),
        )

        name = html.unescape(name).strip()

        if not username:
            continue

        key = username.lower()

        if key in seen:
            continue

        seen.add(key)

        members.append(
            Member(
                username=username,
                name=name or username,
            )
        )

    if not members:
        raise ValueError(
            "README의 스터디 멤버 표에서 "
            "GitHub 사용자명과 이름을 찾지 못했습니다."
        )

    return members


def is_submitted_file(
    path: Path,
    username: str,
) -> bool:
    """
    현재 파일이 자동 생성된 기본 템플릿 그대로인지,
    실제 사용자가 수정한 파일인지 판단한다.

    템플릿 그대로:
        미제출

    템플릿과 다름:
        제출
    """

    language = EXTENSION_TO_LANGUAGE.get(
        path.suffix.lower()
    )

    try:
        content = path.read_text(
            encoding="utf-8"
        )

    except UnicodeDecodeError:
        # 혹시 텍스트가 아닌 파일이 직접 추가된 경우
        return path.stat().st_size > 0

    # generate_daily.py가 관리하지 않는 확장자는
    # 파일에 내용이 있으면 제출로 본다.
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


def solved_problem(
    problem_dir: Path,
    member: Member,
) -> bool:
    """
    한 문제 폴더에서 해당 멤버가 문제를 풀었는지 확인한다.

    예:
    oneul0.java
    oneul0.py

    여러 언어 파일이 있다면
    하나라도 실제 수정되어 있으면 풀이한 것으로 본다.
    """

    username = member.username.lower()

    for path in problem_dir.iterdir():

        if not path.is_file():
            continue

        # 파일 이름이 GitHub 사용자명이어야 한다.
        if path.stem.lower() != username:
            continue

        if is_submitted_file(
            path,
            member.username,
        ):
            return True

    return False


def inferred_date(folder_name: str) -> date:
    """
    MM-DD 형태의 폴더를 실제 날짜 순서로 정렬한다.

    연말 -> 연초를 넘어가는 경우도 어느 정도 대응한다.
    """

    month, day = map(
        int,
        folder_name.split("-"),
    )

    today = datetime.now(
        ZoneInfo("Asia/Seoul")
    ).date()

    candidate = date(
        today.year,
        month,
        day,
    )

    # 현재보다 7일 이상 미래라면
    # 전년도 날짜라고 판단한다.
    if candidate > today + timedelta(days=7):
        candidate = date(
            today.year - 1,
            month,
            day,
        )

    return candidate


def collect_date_dirs() -> list[Path]:
    """
    problem_solve/08-17
    problem_solve/08-18
    ...

    형태의 날짜 폴더를 가져온다.
    """

    if not PROBLEM_ROOT.exists():
        raise FileNotFoundError(
            f"{PROBLEM_ROOT} 폴더가 없습니다."
        )

    date_dirs = [
        path
        for path in PROBLEM_ROOT.iterdir()
        if (
            path.is_dir()
            and DATE_PATTERN.fullmatch(path.name)
        )
    ]

    date_dirs.sort(
        key=lambda path: inferred_date(
            path.name
        )
    )

    if MAX_DAYS > 0:
        date_dirs = date_dirs[
            -MAX_DAYS:
        ]

    return date_dirs


def collect_results(
    members: list[Member],
    date_dirs: list[Path],
) -> dict[str, list[DailyResult]]:
    """
    날짜별 / 사용자별 풀이 수를 계산한다.
    """

    results = {
        member.username: []
        for member in members
    }

    for date_dir in date_dirs:

        # 날짜 폴더 바로 아래의 디렉터리 =
        # 그날의 문제
        problem_dirs = sorted(
            [
                path
                for path in date_dir.iterdir()
                if path.is_dir()
            ],
            key=lambda path: path.name.lower(),
        )

        for member in members:

            solved = sum(
                solved_problem(
                    problem_dir,
                    member,
                )
                for problem_dir in problem_dirs
            )

            results[
                member.username
            ].append(
                DailyResult(
                    date=date_dir.name,
                    solved=solved,
                    total=len(
                        problem_dirs
                    ),
                )
            )

    return results


def escape(value: str) -> str:
    return html.escape(
        value,
        quote=True,
    )


def build_svg(
    members: list[Member],
    date_dirs: list[Path],
    results: dict[
        str,
        list[DailyResult],
    ],
) -> str:
    """
    GitHub Contribution Graph 스타일의 SVG를 만든다.
    """

    cell = 15
    gap = 4

    step = cell + gap

    left = 145
    top = 78

    row_step = 26

    right = 145
    bottom = 58

    columns = max(
        1,
        len(date_dirs),
    )

    width = (
        left
        + columns * step
        + right
    )

    height = (
        top
        + len(members) * row_step
        + bottom
    )

    repository = os.getenv(
        "GITHUB_REPOSITORY",
        "Chwippo-Eleven/ALGO",
    )

    lines = [
        (
            f'<svg '
            f'xmlns="http://www.w3.org/2000/svg" '
            f'xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'width="{width}" '
            f'height="{height}" '
            f'viewBox="0 0 {width} {height}" '
            f'role="img" '
            f'aria-labelledby="title desc">'
        ),

        (
            '<title id="title">'
            '매일알고 알고리즘 잔디'
            '</title>'
        ),

        (
            '<desc id="desc">'
            '날짜별 스터디원의 '
            '알고리즘 문제 풀이 현황'
            '</desc>'
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
            ".title{"
            "font-size:18px;"
            "font-weight:700"
            "}"
        ),

        (
            ".label{"
            "font-size:12px;"
            "font-weight:600"
            "}"
        ),

        (
            ".date,"
            ".count,"
            ".legend{"
            "font-size:10px;"
            "fill:#57606a"
            "}"
        ),

        (
            "@media(prefers-color-scheme:dark){"
            "text{fill:#c9d1d9}"
            ".date,"
            ".count,"
            ".legend{fill:#8b949e}"
            "}"
        ),

        "</style>",

        (
            '<text '
            'x="0" '
            'y="20" '
            'class="title">'
            'Algorithm Grass'
            '</text>'
        ),
    ]

    if not date_dirs:

        lines.extend(
            [
                (
                    '<text '
                    'x="0" '
                    'y="48" '
                    'class="count">'
                    '표시할 날짜 폴더가 없습니다.'
                    '</text>'
                ),
                "</svg>",
            ]
        )

        return "\n".join(lines)

    # -----------------------------
    # 날짜
    # -----------------------------

    for index, date_dir in enumerate(
        date_dirs
    ):

        x = (
            left
            + index * step
            + cell / 2
        )

        y = top - 10

        lines.append(
            (
                f'<text '
                f'x="{x:.1f}" '
                f'y="{y}" '
                f'class="date" '
                f'text-anchor="end" '
                f'transform="rotate('
                f'-45 {x:.1f} {y}'
                f')">'
                f'{escape(date_dir.name)}'
                f'</text>'
            )
        )

    # -----------------------------
    # 멤버별 잔디
    # -----------------------------

    for row, member in enumerate(
        members
    ):

        y = (
            top
            + row * row_step
        )

        member_results = results[
            member.username
        ]

        participation_days = sum(
            result.solved > 0
            for result in member_results
        )

        perfect_days = sum(
            (
                result.total > 0
                and result.solved
                == result.total
            )
            for result in member_results
        )

        profile_url = (
            "https://github.com/"
            + quote(
                member.username,
                safe="",
            )
        )

        lines.append(
            (
                f'<a '
                f'xlink:href="'
                f'{escape(profile_url)}" '
                f'target="_blank">'

                f'<text '
                f'x="0" '
                f'y="{y + 12}" '
                f'class="label">'

                f'{escape(member.name)}'

                f'</text>'
                f'</a>'
            )
        )

        # 각 날짜별 셀
        for column, result in enumerate(
            member_results
        ):

            x = (
                left
                + column * step
            )

            date_url = (
                f"https://github.com/"
                f"{repository}/tree/main/"
                f"problem_solve/"
                f"{quote(result.date, safe='')}"
            )

            tooltip = (
                f"{member.name} "
                f"(@{member.username}) · "
                f"{result.date} · "
                f"{result.solved}/"
                f"{result.total} 문제"
            )

            lines.extend(
                [
                    (
                        f'<a '
                        f'xlink:href="'
                        f'{escape(date_url)}" '
                        f'target="_blank">'
                    ),

                    (
                        f'<rect '
                        f'x="{x}" '
                        f'y="{y}" '
                        f'width="{cell}" '
                        f'height="{cell}" '
                        f'rx="3" '
                        f'fill="'
                        f'{GRASS_COLORS[result.level]}'
                        f'">'
                    ),

                    (
                        f"<title>"
                        f"{escape(tooltip)}"
                        f"</title>"
                    ),

                    "</rect>",
                    "</a>",
                ]
            )

        count_x = (
            left
            + len(date_dirs) * step
            + 10
        )

        lines.append(
            (
                f'<text '
                f'x="{count_x}" '
                f'y="{y + 12}" '
                f'class="count">'
                f'완주 {perfect_days} · '
                f'참여 {participation_days}'
                f'</text>'
            )
        )

    # -----------------------------
    # 범례
    # -----------------------------

    legend_y = (
        top
        + len(members) * row_step
        + 28
    )

    legend_x = left

    lines.append(
        (
            f'<text '
            f'x="{legend_x - 35}" '
            f'y="{legend_y + 11}" '
            f'class="legend">'
            f'0'
            f'</text>'
        )
    )

    for level in range(5):

        x = (
            legend_x
            + level * step
        )

        lines.append(
            (
                f'<rect '
                f'x="{x}" '
                f'y="{legend_y}" '
                f'width="{cell}" '
                f'height="{cell}" '
                f'rx="3" '
                f'fill="'
                f'{GRASS_COLORS[level]}'
                f'"/>'
            )
        )

    lines.append(
        (
            f'<text '
            f'x="{legend_x + 5 * step + 4}" '
            f'y="{legend_y + 11}" '
            f'class="legend">'
            f'100%'
            f'</text>'
        )
    )

    lines.append(
        "</svg>"
    )

    return "\n".join(lines)


def update_readme(
    readme: str,
) -> str:
    """
    README에 잔디 영역을 자동으로 생성한다.

    이미 있으면 해당 영역만 갱신한다.
    """

    block = (
        f"{GRASS_START}\n"
        "## 🌱 알고리즘 잔디\n\n"
        "> 각 칸은 해당 날짜의 필수 문제 풀이 비율을 나타냅니다. "
        "칸을 클릭하면 날짜별 문제 폴더로 이동합니다.\n\n"
        "[![Algorithm Grass](./assets/algorithm-grass.svg)]"
        "(./problem_solve)\n"
        f"{GRASS_END}"
    )

    # 이미 잔디 블록이 존재하는 경우
    if (
        GRASS_START in readme
        and GRASS_END in readme
    ):

        pattern = re.compile(
            re.escape(
                GRASS_START
            )
            + r".*?"
            + re.escape(
                GRASS_END
            ),
            re.DOTALL,
        )

        return pattern.sub(
            block,
            readme,
        )

    # 처음 실행하는 경우
    # 현재 README의 데일리 문제 영역 앞에 삽입한다.
    daily_heading = re.search(
        r"^###\s*🟨",
        readme,
        re.MULTILINE,
    )

    if daily_heading:

        position = daily_heading.start()

        return (
            readme[:position].rstrip()
            + "\n\n<br />\n\n"
            + block
            + "\n\n<br />\n\n"
            + readme[position:].lstrip()
        )

    # 데일리 문제 heading을 찾지 못했다면
    # README 맨 아래에 추가한다.
    return (
        readme.rstrip()
        + "\n\n"
        + block
        + "\n"
    )


def main() -> None:

    if not README_PATH.exists():
        raise FileNotFoundError(
            "README.md가 없습니다."
        )

    readme = README_PATH.read_text(
        encoding="utf-8"
    )

    members = extract_members(
        readme
    )

    date_dirs = collect_date_dirs()

    results = collect_results(
        members,
        date_dirs,
    )

    # SVG 생성
    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        build_svg(
            members,
            date_dirs,
            results,
        )
        + "\n",
        encoding="utf-8",
    )

    # README에 잔디 영역 자동 추가
    README_PATH.write_text(
        update_readme(
            readme
        ),
        encoding="utf-8",
    )

    print(
        f"잔디 생성 완료: "
        f"{len(members)}명 / "
        f"최근 {len(date_dirs)}회 / "
        f"{OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()
