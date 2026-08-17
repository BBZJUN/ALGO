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

# .github는 gitignore 상태를 유지하고
# 상태 파일만 레포 루트에서 관리한다.
STATE_PATH = Path("problem-duty.json")


# =========================================================
# README 자동 생성 영역
# =========================================================

DUTY_START = "<!-- PROBLEM_DUTY:START -->"
DUTY_END = "<!-- PROBLEM_DUTY:END -->"


# =========================================================
# 시간 정책
# =========================================================

KST = ZoneInfo("Asia/Seoul")

# 평일 18시부터 다음 문제 출제 의무 발생
DUTY_CHANGE_TIME = time(
    hour=18,
    minute=0,
)


# =========================================================
# 요일
# =========================================================

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
    """
    README에 현재 등록되어 있는 스터디원만 활성 멤버로 본다.

    반환 예:

    {
        "oneul0": "김기훈",
        "BBZJUN": "강재준",
        ...
    }
    """

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

        members[
            username
        ] = (
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
    """
    다음 평일.

    월 -> 화
    목 -> 금
    금 -> 월
    """

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
    """
    이전 평일.

    월 -> 금
    """

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
    """
    평일이면 그대로 반환하고,
    주말이면 다음 월요일을 반환한다.
    """

    target = current

    while target.weekday() >= 5:

        target += timedelta(
            days=1
        )

    return target


# =========================================================
# 현재 담당 문제가 어느 날짜 문제인지 계산
# =========================================================

def current_problem_date(
    current: datetime,
) -> date:
    """
    현재 담당자가 책임지는 문제 날짜.

    평일 18:00 이전
        → 오늘 문제

    평일 18:00 이후
        → 다음 평일 문제

    금요일 18:00 이후
        → 월요일 문제

    토/일
        → 월요일 문제
    """

    today = current.date()

    # -----------------------------------------
    # 주말
    # -----------------------------------------

    if today.weekday() >= 5:

        return next_or_same_weekday(
            today
        )

    # -----------------------------------------
    # 평일 18시 이전
    # -----------------------------------------

    if (
        current.time()
        < DUTY_CHANGE_TIME
    ):

        return today

    # -----------------------------------------
    # 평일 18시 이후
    # -----------------------------------------

    return next_weekday(
        today
    )


# =========================================================
# 두 평일 사이의 로테이션 횟수 계산
# =========================================================

def weekday_distance(
    start: date,
    target: date,
) -> int:
    """
    start에서 target까지 몇 번의
    평일 담당 전환이 있었는지 계산한다.

    월 -> 화 = 1
    금 -> 월 = 1
    """

    if start == target:
        return 0

    # -----------------------------------------
    # 미래
    # -----------------------------------------

    if target > start:

        cursor = start
        count = 0

        while cursor < target:

            cursor = next_weekday(
                cursor
            )

            count += 1

        return count

    # -----------------------------------------
    # 과거
    # -----------------------------------------

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
    problem-duty.json 로드.

    필요한 구조:

    {
      "order": [...],
      "last_date": "2026-08-17",
      "last_username": "BBZJUN"
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

        file.write(
            "\n"
        )


# =========================================================
# 인원 변동 대응
# =========================================================

def sync_rotation(
    state: dict,
    active_members: dict[str, str],
) -> list[str]:
    """
    기존 로테이션 순서는 최대한 유지한다.

    탈퇴
        → order에는 기록 유지
        → 실제 로테이션에서는 제외

    복귀
        → 기존 order 위치로 자동 복귀

    신규
        → order 맨 뒤에 자동 추가
    """

    full_order = list(
        state["order"]
    )

    known = {
        username.lower()
        for username in full_order
    }

    # =====================================================
    # 신규 멤버
    # =====================================================

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

    state[
        "order"
    ] = full_order

    # =====================================================
    # 현재 README에 존재하는 사람만 활성화
    # =====================================================

    active_lookup = {
        username.lower(): username
        for username
        in active_members
    }

    active_order = []

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
# 로테이션 유틸
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
    """
    현재 담당자 다음의 활성 멤버를 찾는다.

    중간에 탈퇴자가 있으면 자동으로 건너뛴다.
    """

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

    # 상태 파일이 깨져 현재 담당자가
    # order에 없는 경우 첫 활성 멤버 사용
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
        "다음 활성 담당자를 찾지 못했습니다."
    )


# =========================================================
# 특정 문제 날짜의 담당자 계산
# =========================================================

def resolve_duty(
    state: dict,
    active_order: list[str],
    target_date: date,
) -> str:
    """
    상태 파일의 마지막 담당자를 기준으로
    target_date 담당자를 계산한다.

    예:

    last_date     = 2026-08-17
    last_username = BBZJUN

    2026-08-18 담당자
        → yonseeee
    """

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

    # 과거 날짜를 다시 계산해야 하는 상황은
    # 상태 기반 로테이션에서는 허용하지 않는다.
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

    # =====================================================
    # 같은 날짜
    # =====================================================

    if distance == 0:

        # 마지막 담당자가 현재 탈퇴한 상태라면
        # 다음 활성 멤버에게 넘긴다.
        if (
            username.lower()
            not in active_lower
        ):

            return next_active_username(
                full_order,
                active_order,
                username,
            )

        # 대소문자 차이가 있을 수 있으므로
        # active_order의 실제 username 반환
        for active_username in active_order:

            if (
                active_username.lower()
                == username.lower()
            ):

                return active_username

        return username

    # =====================================================
    # 미래 날짜
    # =====================================================

    for _ in range(
        distance
    ):

        username = next_active_username(
            full_order,
            active_order,
            username,
        )

    return username


# =========================================================
# 출력 포맷
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


def member_link(
    username: str,
    active_members: dict[str, str],
) -> str:

    name = active_members.get(
        username,
        username,
    )

    return (
        f"[**{name}**]"
        f"(https://github.com/"
        f"{username})"
    )


# =========================================================
# README 담당자 영역
# =========================================================

def build_duty_block(
    current_date: date,
    current_username: str,
    next_date: date,
    next_username: str,
    active_members: dict[str, str],
    active_order: list[str],
) -> str:

    rotation_names = [
        active_members.get(
            username,
            username,
        )
        for username
        in active_order
    ]

    rotation_text = (
        " → ".join(
            rotation_names
        )
    )

    return "\n".join(
        [
            DUTY_START,

            "## 📌 문제 출제 담당",

            "",

            (
                f"> **현재 담당 · "
                f"{format_date(current_date)} 문제** "
                f"→ "
                f"{member_link(
                    current_username,
                    active_members,
                )}"
            ),

            "",

            (
                f"> **다음 담당 · "
                f"{format_date(next_date)} 문제** "
                f"→ "
                f"{member_link(
                    next_username,
                    active_members,
                )}"
            ),

            "",

            (
                "> 담당은 평일 **18:00**에 "
                "다음 문제 담당자로 전환됩니다."
            ),

            "",

            (
                f"<sub>"
                f"{rotation_text}"
                f"</sub>"
            ),

            DUTY_END,
        ]
    )


# =========================================================
# README 갱신
# =========================================================

def update_readme(
    text: str,
    block: str,
) -> str:

    # =====================================================
    # 기존 담당 영역이 있으면 교체
    # =====================================================

    if (
        DUTY_START in text
        and DUTY_END in text
    ):

        pattern = re.compile(
            re.escape(
                DUTY_START
            )
            + r".*?"
            + re.escape(
                DUTY_END
            ),
            re.DOTALL,
        )

        return pattern.sub(
            lambda _: block,
            text,
        )

    # =====================================================
    # 잔디가 있으면 잔디 아래에 삽입
    # =====================================================

    grass_end = (
        "<!-- ALGORITHM_ACTIVITY:END -->"
    )

    if grass_end in text:

        position = (
            text.index(
                grass_end
            )
            + len(
                grass_end
            )
        )

        return (
            text[:position]
            + "\n\n<br />\n\n"
            + block
            + text[position:]
        )

    # =====================================================
    # 잔디가 없으면 데일리 문제 앞
    # =====================================================

    daily_heading = re.search(
        r"^###\s*🟨",
        text,
        re.MULTILINE,
    )

    if daily_heading:

        position = (
            daily_heading.start()
        )

        return (
            text[:position].rstrip()
            + "\n\n"
            + block
            + "\n\n<br />\n\n"
            + text[position:].lstrip()
        )

    # =====================================================
    # 둘 다 없으면 README 끝
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

    if not README_PATH.exists():

        raise FileNotFoundError(
            "README.md가 없습니다."
        )

    # =====================================================
    # README
    # =====================================================

    readme = README_PATH.read_text(
        encoding="utf-8"
    )

    active_members = get_active_members(
        readme
    )

    # =====================================================
    # 상태
    # =====================================================

    state = load_state()

    active_order = sync_rotation(
        state,
        active_members,
    )

    # =====================================================
    # 현재 시각 기준 담당 문제 날짜
    # =====================================================

    current_time = now_kst()

    duty_date = current_problem_date(
        current_time
    )

    current_username = resolve_duty(
        state,
        active_order,
        duty_date,
    )

    # =====================================================
    # 다음 담당
    # =====================================================

    next_date = next_weekday(
        duty_date
    )

    next_username = next_active_username(
        state["order"],
        active_order,
        current_username,
    )

    # =====================================================
    # README
    # =====================================================

    block = build_duty_block(
        duty_date,
        current_username,
        next_date,
        next_username,
        active_members,
        active_order,
    )

    updated_readme = update_readme(
        readme,
        block,
    )

    README_PATH.write_text(
        updated_readme,
        encoding="utf-8",
    )

    # =====================================================
    # 현재 상태를 다음 실행 기준점으로 저장
    # =====================================================

    state[
        "last_date"
    ] = duty_date.isoformat()

    state[
        "last_username"
    ] = current_username

    save_state(
        state
    )

    # =====================================================
    # Action 로그
    # =====================================================

    print(
        "실행 시각: "
        f"{current_time.strftime('%Y-%m-%d %H:%M:%S %Z')}"
    )

    print(
        "활성 로테이션: "
        + " → ".join(
            active_members[
                username
            ]
            for username
            in active_order
        )
    )

    print(
        "현재 담당: "
        f"{active_members[current_username]} "
        f"({format_date(duty_date)} 문제)"
    )

    print(
        "다음 담당: "
        f"{active_members[next_username]} "
        f"({format_date(next_date)} 문제)"
    )


if __name__ == "__main__":
    main()
