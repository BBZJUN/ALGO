import java.util.*;

class Solution {
    public int solution(int[] queue1, int[] queue2) {
        int answer = 0;
        
        Queue<Integer> q1 = new ArrayDeque<>();
        Queue<Integer> q2 = new ArrayDeque<>();
        
        long sum1=0, sum2=0;
        for(int value:queue1){
            sum1+=value;
            q1.offer(value);
        }
        for(int value:queue2){
            sum2+=value;
            q2.offer(value);
        }
        
        // 모든 큐에 들어있는 원소의 합의 절반 값 구하기
        long half = (sum1+sum2)/2;
        

        // 두 큐의 합이 다른 동안
        while(sum1!=sum2){
            //합이 더 큰 큐에서 poll 한 뒤, 합이 더 작은 큐에 offer
            if(sum1<half){
                int elem=q2.poll();
                q1.offer(elem);
                
                sum1+=elem; sum2-=elem;
            }else if(sum2<half){
                int elem=q1.poll();
                q2.offer(elem);
                
                sum1-=elem; sum2+=elem;
            }
            answer++;
            if(answer>queue1.length*4){//충분히 반복했는데도 합이 같아지지 않음
                return -1;
            }
        }
        
        return answer;
    }
}
