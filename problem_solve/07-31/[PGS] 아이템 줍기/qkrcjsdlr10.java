import java.util.*;

class Solution {

    static class Node {
        int y;
        int x;
        int dir;
        int dist;

        Node(int y, int x, int dir, int dist) {
            this.y = y;
            this.x = x;
            this.dir = dir;
            this.dist = dist;
        }
    }

    static int[] dx = {0, 1, 0, -1};
    static int[] dy = {-1, 0, 1, 0};

    public int solution(int[][] rectangle, int characterX, int characterY,
                        int itemX, int itemY) {

        int[][] map = new int[110][110];

        // 테두리 생성 (2배 확장)
        for (int[] rec : rectangle) {

            int sx = rec[0] * 2;
            int sy = rec[1] * 2;
            int ex = rec[2] * 2;
            int ey = rec[3] * 2;

            for (int x = sx; x <= ex; x++) {
                for (int y = sy; y <= ey; y++) {
                    map[y][x] = 1;
                }
            }
        }

        // 내부 제거
        for (int[] rec : rectangle) {

            int sx = rec[0] * 2;
            int sy = rec[1] * 2;
            int ex = rec[2] * 2;
            int ey = rec[3] * 2;

            for (int x = sx + 1; x < ex; x++) {
                for (int y = sy + 1; y < ey; y++) {
                    map[y][x] = 0;
                }
            }
        }


        boolean[][][] visited = new boolean[110][110][4];

        int sy = characterY * 2;
        int sx = characterX * 2;

        int ey = itemY * 2;
        int ex = itemX * 2;


        Queue<Node> q = new ArrayDeque<>();

        // 처음 방향 4개 모두 가능하게 시작
        for (int d = 0; d < 4; d++) {
            int ny = sy + dy[d];
            int nx = sx + dx[d];

            if (map[ny][nx] == 1) {
                visited[sy][sx][d] = true;
                q.offer(new Node(sy, sx, d, 0));
            }
        }


        while (!q.isEmpty()) {

            Node cur = q.poll();

            if (cur.y == ey && cur.x == ex) {
                return cur.dist / 2;
            }


            for (int nd = 0; nd < 4; nd++) {

                int ny = cur.y + dy[nd];
                int nx = cur.x + dx[nd];


                if (map[ny][nx] == 0) continue;


                if (visited[ny][nx][nd]) continue;


                visited[ny][nx][nd] = true;

                q.offer(new Node(
                        ny,
                        nx,
                        nd,
                        cur.dist + 1
                ));
            }
        }

        return 0;
    }
}