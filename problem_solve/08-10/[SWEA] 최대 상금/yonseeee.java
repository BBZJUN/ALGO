
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.util.HashSet;
import java.util.Set;
import java.util.StringTokenizer;

class Solution {
	
	static char[] nums;
	static Set<String>[] visited;
	static int max;
	public static void main(String[] args) throws Exception{
		
		BufferedReader br = new BufferedReader(new InputStreamReader(System.in));
		
		int T=Integer.parseInt(br.readLine());
		
		for(int tc=1;tc<=T;tc++) {
			StringTokenizer st = new StringTokenizer(br.readLine());
			
			nums=st.nextToken().toCharArray();
			int swap_cnt=Integer.parseInt(st.nextToken());
			
			visited=new HashSet[swap_cnt+1];
			
			max=0;
			
			for(int i=0;i<=swap_cnt;i++) {
				visited[i]=new HashSet<>();
			}
			
			dfs(0, swap_cnt);
			
			System.out.println(("#"+tc+" "+max));
				
		}

	}
	private static void swap(int i, int j) {
		char tmp=nums[i];
		nums[i]=nums[j];
		nums[j]=tmp;
	}
	
	
	private static void dfs(int cur_cnt, int total_cnt) {
		String current=new String(nums);
		if(visited[cur_cnt].contains(current)) {
			return;
		}
		visited[cur_cnt].add(current);
		
		if(cur_cnt==total_cnt) {
			max=Math.max(max, Integer.parseInt(current));
			return;
		}
		
		for(int i=0;i<nums.length;i++) {
			for(int j=i+1;j<nums.length;j++) {
				swap(i,j);
				dfs(cur_cnt+1, total_cnt);
				swap(i,j);
			}
		}
	}

}
