import java.util.*;

class Solution {
    public int solution(int[][] triangle) {
        int answer = 0;
        
        int n=triangle.length;
        
        int[][]dp=new int[n][n];
        
        for(int i=0;i<n;i++){
            for(int j=0;j<n;j++){
                dp[i][j]=-1;
            }
        }
        
        dp[0][0]=triangle[0][0];
        
        for(int i=1;i<n;i++){
            for(int j=0;j<triangle[i].length;j++){
                if(j==0){
                    dp[i][j]=dp[i-1][j]+triangle[i][j];
                    continue;
                }
                if(j==i){
                    dp[i][j]=dp[i-1][j-1]+triangle[i][j];
                    continue;
                }
                
                if(dp[i][j]==-1){
                    dp[i][j]=dp[i-1][j-1]+triangle[i][j];
                }
                dp[i][j]=Math.max(dp[i][j], dp[i-1][j]+triangle[i][j]);
                
            }
        }
        for(int i=0;i<n;i++){
            for(int j=0;j<n;j++){
                System.out.print(dp[i][j]);
            }
            System.out.println();
        }
        
        int max=Integer.MIN_VALUE;
        for(int value:dp[n-1]){
            max=Math.max(max,value);
        }
        return max;
    }
}
