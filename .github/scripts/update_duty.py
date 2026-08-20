from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import html
import json
import re


# =========================================================
# 경로
# =========================================================

README_PATH = Path("README.md")

# 로테이션 상태
# Git에서 추적해야 한다.
STATE_PATH = Path("problem-duty.json")

# README가 참조할 자동 생성 이미지
SVG_PATH = Path("problem-duty.svg")


# =========================================================
# 시간 정책
# =========================================================

KST = ZoneInfo("Asia/Seoul")

# 평일 18시부터 다음 평일 문제 출제 담당으로 전환
DUTY_CHANGE_TIME = time(
    hour=18,
    minute=0,
)


WEEKDAY_NAMES = [
    "월",
    "화",
    "수",
    "목",
    "금",
    "토",
    "일",
]


# =========================================================
# README 멤버 추출
#
# 예:
#
# <a href="https://github.com/oneul0">
#   <b>김기훈</b>
# </a>
# =========================================================

MEMBER_PATTERN = re.compile(
    r'<a\s+href=["\']https://github\.com/'
    r'(?P<username>[^/"\'?#]+)["\'][^>]*>'
    r'\s*<b>(?P<name>.*?)</b>\s*</a>',
    re.IGNORECASE | re.DOTALL,
)


# =========================================================
# 현재 시각
# =========================================================

def now_kst() -> datetime:
    return datetime.now(KST)


# =========================================================
# README에서 현재 활성 멤버 추출
# =========================================================

def get_active_members(
    readme: str,
) -> dict[str, str]:

    members: dict[str, str] = {}

    for match in MEMBER_PATTERN.finditer(
        readme
    ):
        username = html.unescape(
            match.group("username")
        ).strip()

        name = re.sub(
            r"<[^>]+>",
            "",
            match.group("name"),
        )

        name = html.unescape(
            name
        ).strip()

        if not username:
            continue

        members[username] = (
            name
            or username
        )

    if not members:
        raise ValueError(
            "README에서 활성 스터디 멤버를 "
            "찾지 못했습니다."
        )

    return members


# =========================================================
# 평일 계산
# =========================================================

def next_weekday(
    current: date,
) -> date:

    target = (
        current
        + timedelta(days=1)
    )

    while target.weekday() >= 5:
        target += timedelta(
            days=1
        )

    return target


def previous_weekday(
    current: date,
) -> date:

    target = (
        current
        - timedelta(days=1)
    )

    while target.weekday() >= 5:
        target -= timedelta(
            days=1
        )

    return target


def next_or_same_weekday(
    current: date,
) -> date:

    target = current

    while target.weekday() >= 5:
        target += timedelta(
            days=1
        )

    return target


# =========================================================
# 현재 담당 문제 날짜
# =========================================================

def current_problem_date(
    current: datetime,
) -> date:
    """
    평일 18:00 이전
        -> 오늘 문제 담당

    평일 18:00 이후
        -> 다음 평일 문제 담당

    금요일 18:00 이후
        -> 월요일 문제 담당

    주말
        -> 월요일 문제 담당
    """

    today = current.date()

    if today.weekday() >= 5:
        return next_or_same_weekday(
            today
        )

    if (
        current.time()
        < DUTY_CHANGE_TIME
    ):
        return today

    return next_weekday(
        today
    )


# =========================================================
# 두 평일 사이 로테이션 횟수
# =========================================================

def weekday_distance(
    start: date,
    target: date,
) -> int:

    if start == target:
        return 0

    if target > start:
        cursor = start
        count = 0

        while cursor < target:
            cursor = next_weekday(
                cursor
            )

            count += 1

        return count

    cursor = start
    count = 0

    while cursor > target:
        cursor = previous_weekday(
            cursor
        )

        count -= 1

    return count


# =========================================================
# 상태 파일
# =========================================================

def load_state() -> dict:
    """
    problem-duty.json

    {
      "order": [...],
      "last_date": "2026-08-20",
      "last_username": "Sangyoon-Shin"
    }
    """

    if not STATE_PATH.exists():
        raise FileNotFoundError(
            f"{STATE_PATH}가 없습니다."
        )

    with STATE_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        state = json.load(
            file
        )

    required = {
        "order",
        "last_date",
        "last_username",
    }

    missing = (
        required
        - state.keys()
    )

    if missing:
        raise ValueError(
            "problem-duty.json에 "
            "필수 필드가 없습니다: "
            + ", ".join(
                sorted(missing)
            )
        )

    if not isinstance(
        state["order"],
        list,
    ):
        raise ValueError(
            "problem-duty.json의 "
            "order는 배열이어야 합니다."
        )

    if not state["order"]:
        raise ValueError(
            "problem-duty.json의 "
            "order가 비어 있습니다."
        )

    return state


def save_state(
    state: dict,
) -> None:

    with STATE_PATH.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            state,
            file,
            ensure_ascii=False,
            indent=2,
        )

        file.write("\n")


# =========================================================
# 인원 변동 대응
# =========================================================

def sync_rotation(
    state: dict,
    active_members: dict[str, str],
) -> list[str]:
    """
    기존 order는 유지한다.

    탈퇴자
        -> 기존 order에는 남음
        -> 현재 로테이션에서는 제외

    복귀자
        -> 기존 위치로 복귀

    신규 멤버
        -> order 마지막에 추가
    """

    full_order = list(
        state["order"]
    )

    known = {
        username.lower()
        for username
        in full_order
    }

    # 신규 멤버 추가
    for username in active_members:

        key = username.lower()

        if key in known:
            continue

        full_order.append(
            username
        )

        known.add(
            key
        )

        print(
            "신규 멤버 로테이션 추가: "
            f"{active_members[username]} "
            f"(@{username})"
        )

    state["order"] = full_order

    active_lookup = {
        username.lower(): username
        for username
        in active_members
    }

    active_order: list[str] = []

    for username in full_order:

        real_username = (
            active_lookup.get(
                username.lower()
            )
        )

        if real_username is None:
            continue

        active_order.append(
            real_username
        )

    if not active_order:
        raise ValueError(
            "현재 활성 로테이션 멤버가 없습니다."
        )

    return active_order


# =========================================================
# 로테이션
# =========================================================

def find_order_index(
    order: list[str],
    username: str,
) -> int | None:

    target = username.lower()

    for index, candidate in enumerate(
        order
    ):
        if (
            candidate.lower()
            == target
        ):
            return index

    return None


def next_active_username(
    full_order: list[str],
    active_order: list[str],
    current_username: str,
) -> str:

    if not active_order:
        raise ValueError(
            "활성 멤버가 없습니다."
        )

    active_lookup = {
        username.lower(): username
        for username
        in active_order
    }

    current_index = find_order_index(
        full_order,
        current_username,
    )

    if current_index is None:
        return active_order[0]

    total = len(
        full_order
    )

    for offset in range(
        1,
        total + 1,
    ):
        candidate = full_order[
            (
                current_index
                + offset
            )
            % total
        ]

        active_username = (
            active_lookup.get(
                candidate.lower()
            )
        )

        if active_username:
            return active_username

    raise ValueError(
        "다음 활성 담당자를 "
        "찾지 못했습니다."
    )


# =========================================================
# 특정 날짜 담당자 계산
# =========================================================

def resolve_duty(
    state: dict,
    active_order: list[str],
    target_date: date,
) -> str:

    last_date = date.fromisoformat(
        state["last_date"]
    )

    username = state[
        "last_username"
    ]

    full_order = state[
        "order"
    ]

    distance = weekday_distance(
        last_date,
        target_date,
    )

    if distance < 0:
        raise ValueError(
            "problem-duty.json의 last_date가 "
            "현재 담당 문제 날짜보다 미래입니다."
        )

    active_lower = {
        item.lower()
        for item
        in active_order
    }

    # 같은 날짜
    if distance == 0:

        if (
            username.lower()
            not in active_lower
        ):
            return next_active_username(
                full_order,
                active_order,
                username,
            )

        for active_username in active_order:

            if (
                active_username.lower()
                == username.lower()
            ):
                return active_username

        return username

    # 미래 날짜
    for _ in range(
        distance
    ):
        username = (
            next_active_username(
                full_order,
                active_order,
                username,
            )
        )

    return username


# =========================================================
# 표시
# =========================================================

def format_date(
    target: date,
) -> str:

    weekday = WEEKDAY_NAMES[
        target.weekday()
    ]

    return (
        f"{target.month:02d}-"
        f"{target.day:02d} "
        f"({weekday})"
    )


def escape_svg(
    value: str,
) -> str:
    return html.escape(
        value,
        quote=True,
    )


# =========================================================
# SVG 생성
# =========================================================

def build_svg(
    problem_date: date,
    current_username: str,
    next_date: date,
    next_username: str,
    active_order: list[str],
    active_members: dict[str, str],
) -> str:

    current_name = (
        active_members.get(
            current_username,
            current_username,
        )
    )

    next_name = (
        active_members.get(
            next_username,
            next_username,
        )
    )

    rotation = " → ".join(
        active_members.get(
            username,
            username,
        )
        for username
        in active_order
    )

    current_date_text = escape_svg(
        format_date(problem_date)
    )

    next_date_text = escape_svg(
        format_date(next_date)
    )

    current_name_text = escape_svg(
        current_name
    )

    next_name_text = escape_svg(
        next_name
    )

    current_username_text = escape_svg(
        current_username
    )

    next_username_text = escape_svg(
        next_username
    )

    rotation_text = escape_svg(
        rotation
    )

    return f"""\
<svg
    xmlns="http://www.w3.org/2000/svg"
    width="1000"
    height="230"
    viewBox="0 0 1000 230"
    role="img"
    aria-labelledby="title desc"
>
  <title id="title">문제 출제 담당</title>
  <desc id="desc">
    현재 문제 출제 담당자와 다음 담당자
  </desc>

  <rect
      x="0"
      y="0"
      width="1000"
      height="230"
      rx="16"
      fill="#0d1117"
  />

  <text
      x="36"
      y="44"
      fill="#f0f6fc"
      font-size="22"
      font-weight="700"
      font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
  >
    문제 출제 담당
  </text>

  <text
      x="36"
      y="90"
      fill="#8b949e"
      font-size="17"
      font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
  >
    현재 담당 · {current_date_text} 문제
  </text>

  <text
      x="335"
      y="90"
      fill="#f0f6fc"
      font-size="20"
      font-weight="700"
      font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
  >
    {current_name_text} (@{current_username_text})
  </text>

  <text
      x="36"
      y="132"
      fill="#8b949e"
      font-size="17"
      font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
  >
    다음 담당 · {next_date_text} 문제
  </text>

  <text
      x="335"
      y="132"
      fill="#f0f6fc"
      font-size="20"
      font-weight="700"
      font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
  >
    {next_name_text} (@{next_username_text})
  </text>

  <line
      x1="36"
      y1="158"
      x2="964"
      y2="158"
      stroke="#30363d"
  />

  <text
      x="36"
      y="190"
      fill="#8b949e"
      font-size="14"
      font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
  >
    평일 18:00 전환
  </text>

  <text
      x="170"
      y="190"
      fill="#c9d1d9"
      font-size="14"
      font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
  >
    {rotation_text}
  </text>
</svg>
"""


def write_if_changed(
    path: Path,
    content: str,
) -> bool:

    if path.exists():

        old_content = path.read_text(
            encoding="utf-8"
        )

        if old_content == content:
            return False

    path.write_text(
        content,
        encoding="utf-8",
    )

    return True


# =========================================================
# 실행
# =========================================================

def main() -> None:

    if not README_PATH.exists():
        raise FileNotFoundError(
            "README.md가 없습니다."
        )

    readme = README_PATH.read_text(
        encoding="utf-8"
    )

    # README는 읽기만 한다.
    # 더 이상 수정하지 않는다.
    active_members = (
        get_active_members(
            readme
        )
    )

    state = load_state()

    active_order = sync_rotation(
        state,
        active_members,
    )

    current = now_kst()

    problem_date = (
        current_problem_date(
            current
        )
    )

    current_username = (
        resolve_duty(
            state,
            active_order,
            problem_date,
        )
    )

    next_date = next_weekday(
        problem_date
    )

    next_username = (
        next_active_username(
            state["order"],
            active_order,
            current_username,
        )
    )

    # 현재 계산 결과를 다음 실행의 기준으로 저장
    state["last_date"] = (
        problem_date.isoformat()
    )

    state["last_username"] = (
        current_username
    )

    save_state(
        state
    )

    svg = build_svg(
        problem_date,
        current_username,
        next_date,
        next_username,
        active_order,
        active_members,
    )

    svg_changed = (
        write_if_changed(
            SVG_PATH,
            svg,
        )
    )

    print()
    print(
        "현재 담당: "
        f"{format_date(problem_date)} "
        f"{active_members.get(current_username, current_username)} "
        f"(@{current_username})"
    )

    print(
        "다음 담당: "
        f"{format_date(next_date)} "
        f"{active_members.get(next_username, next_username)} "
        f"(@{next_username})"
    )

    if svg_changed:
        print(
            f"SVG 업데이트: {SVG_PATH}"
        )
    else:
        print(
            "SVG 변경 사항 없음"
        )


if __name__ == "__main__":
    main()
