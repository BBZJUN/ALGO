from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import re


README_PATH = Path("README.md")

STATE_PATH = Path(
    ".github/problem-duty.json"
)

DUTY_START = (
    "<!-- PROBLEM_DUTY:START -->"
)

DUTY_END = (
    "<!-- PROBLEM_DUTY:END -->"
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
# =========================================================

MEMBER_PATTERN = re.compile(
    r'<a\s+href=["\']'
    r'https://github\.com/'
    r'(?P<username>[^/"\'?#]+)'
    r'["\'][^>]*>'
    r'\s*<b>'
    r'(?P<name>.*?)'
    r'</b>\s*</a>',
    re.IGNORECASE
    | re.DOTALL,
)


def get_active_members(
    readme: str,
) -> dict[str, str]:
    """
    README의 현재 스터디 멤버를 읽는다.

    반환:

    {
        "oneul0": "김기훈",
        "BBZJUN": "강재준",
        ...
    }

    즉 README에 존재하는 사람이
    현재 활성 멤버다.
    """

    members: dict[
        str,
        str,
    ] = {}

    for match in MEMBER_PATTERN.finditer(
        readme
    ):

        username = (
            match
            .group("username")
            .strip()
        )

        name = re.sub(
            r"<[^>]+>",
            "",
            match.group("name"),
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
            "README에서 스터디 멤버를 "
            "찾지 못했습니다."
        )

    return members


# =========================================================
# 날짜
# =========================================================

def today_kst() -> date:
    return datetime.now(
        ZoneInfo("Asia/Seoul")
    ).date()


def next_weekday(
    current: date,
) -> date:
    """
    다음 스터디 날짜.

    월 -> 화
    목 -> 금
    금 -> 월
    """

    target = (
        current
        + timedelta(days=1)
    )

    while (
        target.weekday()
        >= 5
    ):
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

    while (
        target.weekday()
        >= 5
    ):
        target -= timedelta(
            days=1
        )

    return target


def normalize_to_weekday(
    target: date,
) -> date:
    """
    주말에 수동 실행한 경우
    다음 월요일을 기준으로 보여준다.
    """

    while (
        target.weekday()
        >= 5
    ):
        target += timedelta(
            days=1
        )

    return target


def weekday_distance(
    start: date,
    target: date,
) -> int:
    """
    두 날짜 사이의 스터디 회차 수.

    금요일 -> 월요일 = 1
    """

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
# 상태
# =========================================================

def load_state() -> dict:
    """
    마지막 담당자와 전체 로테이션 순서를 읽는다.
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
            "필수 값이 없습니다: "
            + ", ".join(
                sorted(missing)
            )
        )

    return state


def save_state(
    state: dict,
) -> None:

    STATE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

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
# 인원 변동 반영
# =========================================================

def sync_rotation(
    state: dict,
    active_members: dict[str, str],
) -> list[str]:
    """
    로테이션과 현재 README 멤버를 동기화한다.

    1. 기존 멤버
       → 기존 순서 유지

    2. 탈퇴한 멤버
       → order에는 기록을 남기되
         실제 로테이션에서는 제외

       이렇게 해야 나중에 복귀했을 때
       원래 자리를 유지할 수 있다.

    3. 신규 멤버
       → order 마지막에 추가
    """

    order = list(
        state["order"]
    )

    known_lower = {
        username.lower()
        for username in order
    }

    # -----------------------------------------
    # 신규 멤버 자동 추가
    # -----------------------------------------

    for username in active_members:

        if (
            username.lower()
            not in known_lower
        ):

            order.append(
                username
            )

            known_lower.add(
                username.lower()
            )

            print(
                "신규 멤버 로테이션 추가: "
                f"{active_members[username]} "
                f"(@{username})"
            )

    state[
        "order"
    ] = order

    # -----------------------------------------
    # README에 현재 존재하는 멤버만
    # 실제 로테이션으로 사용
    # -----------------------------------------

    active_lower = {
        username.lower(): username
        for username in active_members
    }

    active_order = []

    for username in order:

        real_username = (
            active_lower.get(
                username.lower()
            )
        )

        if real_username:

            active_order.append(
                real_username
            )

    if not active_order:

        raise ValueError(
            "활성 로테이션 멤버가 없습니다."
        )

    return active_order


# =========================================================
# 다음 담당자
# =========================================================

def find_order_index(
    order: list[str],
    username: str,
) -> int | None:

    username_lower = (
        username.lower()
    )

    for index, item in enumerate(
        order
    ):

        if (
            item.lower()
            == username_lower
        ):
            return index

    return None


def next_active_username(
    full_order: list[str],
    active_order: list[str],
    current_username: str,
) -> str:
    """
    현재 담당자 다음의 '활성 멤버'를 찾는다.

    탈퇴자는 자동 건너뛴다.
    """

    if not active_order:

        raise ValueError(
            "활성 멤버가 없습니다."
        )

    active_lower = {
        username.lower(): username
        for username in active_order
    }

    current_index = (
        find_order_index(
            full_order,
            current_username,
        )
    )

    # -----------------------------------------
    # 마지막 담당자가 order에 없는 예외
    # -----------------------------------------

    if current_index is None:

        return active_order[0]

    total = len(
        full_order
    )

    # 한 바퀴 돌며 다음 활성 멤버 탐색
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
            active_lower.get(
                candidate.lower()
            )
        )

        if active_username:

            return active_username

    raise ValueError(
        "다음 담당자를 찾지 못했습니다."
    )


# =========================================================
# 현재 담당자 계산
# =========================================================

def resolve_today_duty(
    state: dict,
    active_order: list[str],
    target_date: date,
) -> str:
    """
    last_date / last_username을 기준으로
    오늘 담당자를 계산한다.

    날짜가 여러 날 지나도
    평일 회차만큼 자동으로 앞으로 이동한다.
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

    # =====================================================
    # 같은 날
    # =====================================================

    if distance == 0:

        # 마지막 담당자가 탈퇴했다면
        # 다음 활성 멤버에게 넘긴다.
        active_lower = {
            item.lower()
            for item in active_order
        }

        if (
            username.lower()
            not in active_lower
        ):

            username = (
                next_active_username(
                    full_order,
                    active_order,
                    username,
                )
            )

        return username

    # =====================================================
    # 미래
    # =====================================================

    if distance > 0:

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

    raise ValueError(
        "상태 파일의 last_date가 "
        "현재 날짜보다 미래입니다."
    )


# =========================================================
# Markdown
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
        for username in active_order
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
                f"> **오늘 · "
                f"{format_date(current_date)}** "
                f"→ "
                f"{member_link(
                    current_username,
                    active_members,
                )}"
            ),

            "",

            (
                f"> **다음 · "
                f"{format_date(next_date)}** "
                f"→ "
                f"{member_link(
                    next_username,
                    active_members,
                )}"
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
# README 수정
# =========================================================

def update_readme(
    text: str,
    block: str,
) -> str:

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

    # -----------------------------------------
    # 잔디 아래에 담당자 영역 삽입
    # -----------------------------------------

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

    # -----------------------------------------
    # 잔디가 없으면 데일리 문제 앞
    # -----------------------------------------

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

    readme = (
        README_PATH.read_text(
            encoding="utf-8"
        )
    )

    # =====================================================
    # 현재 멤버
    # =====================================================

    active_members = (
        get_active_members(
            readme
        )
    )

    # =====================================================
    # 로테이션 상태
    # =====================================================

    state = load_state()

    active_order = (
        sync_rotation(
            state,
            active_members,
        )
    )

    # =====================================================
    # 오늘
    # =====================================================

    current_date = (
        normalize_to_weekday(
            today_kst()
        )
    )

    current_username = (
        resolve_today_duty(
            state,
            active_order,
            current_date,
        )
    )

    # =====================================================
    # 다음 담당자
    # =====================================================

    next_date = next_weekday(
        current_date
    )

    next_username = (
        next_active_username(
            state["order"],
            active_order,
            current_username,
        )
    )

    # =====================================================
    # README
    # =====================================================

    block = build_duty_block(
        current_date,
        current_username,
        next_date,
        next_username,
        active_members,
        active_order,
    )

    updated_readme = (
        update_readme(
            readme,
            block,
        )
    )

    README_PATH.write_text(
        updated_readme,
        encoding="utf-8",
    )

    # =====================================================
    # 상태 갱신
    #
    # 오늘의 담당자를 다음 실행의 기준점으로 저장
    # =====================================================

    state[
        "last_date"
    ] = current_date.isoformat()

    state[
        "last_username"
    ] = current_username

    save_state(
        state
    )

    # =====================================================
    # 로그
    # =====================================================

    print(
        "현재 활성 로테이션: "
        + " → ".join(
            active_members[
                username
            ]
            for username
            in active_order
        )
    )

    print(
        f"오늘 담당자: "
        f"{active_members[current_username]}"
    )

    print(
        f"다음 담당자: "
        f"{active_members[next_username]} "
        f"({format_date(next_date)})"
    )


if __name__ == "__main__":
    main()
