### CartPole 환경 사용
# - openAI에서 만든 강화학습 테스트하기 좋은 환경인, GYM 라이브러리에 포함된 다양한 환경 중 하나
# - CartPole 문제 : 막대기 pole이 45도 이상 기울어져서 넘어지지 않도록 밑에 있는 카트를 움직여 막대의 균형을 잡는 문제
# - 상태 벡터 : 카트 위치, 카트 속도, 막대 각도, 막대의 각속도
# - action : 왼쪽으로 움직임, 오른쪽으로 움직임
 
### 라이브러리 로드
import gym # 환경 가져오기
import collections # transition을 저장하는 buffer 관련 라이브러리
import random
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import numpy as np

### Hyperparameters
learning_rate = 0.0005
gamma         = 0.98 # 미래 reward에 대한 반영값
buffer_limit  = 50000 # 최근 50000개의 transition(t시점의 상태, t시점의 action, t시점의 보상, t+1시점의 상태)을 버퍼에 저장해두고 재사용함. → replay buffer
batch_size    = 32


### DQN 정의 및 학습
# 딥q러닝 학습 시 익스피리언스 리플레이 기법 사용 (경험을 축적하여 사용)
class ReplayBuffer():
    def __init__(self):
        ### TODO 1 : 설정한 size를 자동으로 유지해주는 queue 설정 : https://docs.python.org/ko/3/library/collections.html#collections.deque 참고
        self.buffer = collections.deque(maxlen=buffer_limit)
        ### 1 END
        
    # buffer에 transition 넣기
    def put(self, transition):
        self.buffer.append(transition)
         
    # buffer에서 랜덤하게 n개의 쌓여있는 transition 뽑기
    def sample(self, n):
        mini_batch = random.sample(self.buffer, n)
        s_lst, a_lst, r_lst, s_prime_lst, done_mask_lst = [], [], [], [], []
         
        # mini_batch 크기만큼 buffer에서 랜덤하게 추출
        for transition in mini_batch:
            s, a, r, s_prime, done_mask = transition
            s_lst.append(s)
            a_lst.append([a])
            r_lst.append([r])
            s_prime_lst.append(s_prime)
            done_mask_lst.append([done_mask])
 
        return torch.tensor(s_lst, dtype=torch.float), torch.tensor(a_lst), torch.tensor(r_lst), torch.tensor(s_prime_lst, dtype=torch.float), torch.tensor(done_mask_lst)
     
    def size(self):
        return len(self.buffer)
    

# q network 설계
class Qnet(nn.Module):
    def __init__(self):
        ### TODO 2 : 3레이어 fully connected nn 설정 layer2의 size는 128로 설정
        super(Qnet, self).__init__()
        self.fc1 = nn.Linear(4, 128) # 카트 위치, 카트 속도, 막대 각도, 막대의 각속도 4개의 input
        self.fc2 = nn.Linear(128, 128)
        self.fc3 = nn.Linear(128, 2) # 왼쪽, 오른쪽 움직임 action이므로 2개 output
        ### 2 END
 
    def forward(self, x):
        # TODO 3 : 1,2 layer의 activation은 relu로 설정
        x = F.relu(self.fc1(x))
        x = F.relu(self.fc2(x))
        x = self.fc3(x)
        ### 3 END
        return x
     
    # epsilon greedy를 적용해서 action 결정 (epsilon보다 작은 값이 랜덤하게 뽑히면 랜덤하게 action 결정, 그 외에는 max value인 action으로 결정)
    def sample_action(self, obs, epsilon):
        out = self.forward(obs)
        coin = random.random()
        # TODO 4 : epsilon greedy 설정. 
        if coin < epsilon:
            #  https://docs.python.org/ko/3/library/random.html 참고
            return random.randint(0,1)
        else :
            # self.forward의 결과를 활용해 action 0 혹은 1(python int)이 나와야한다.
            return out.argmax().item()
        ### 4 END


# cartpole 환경 로드
env = gym.make('CartPole-v1')
    
# q와 q target모두 qnet으로 정의
q = Qnet()
q_target = Qnet()
    
# q_target은 q의 파라미터를 주기적으로 복사해서 정답지를 바꿈. (타겟 네트워크 기법 활용)
q_target.load_state_dict(q.state_dict())

# 익스피리언스 리플레이 기법 활용
memory = ReplayBuffer()

print_interval = 20
score = 0.0 
optimizer = optim.Adam(q.parameters(), lr=learning_rate)

# 에피소드 5000번 수행
for n_epi in range(5000):
    # epsilon 값은 처음에는 0.08에서 시작, 점차 에피소드 진행될수록 0.01로 낮추기 위함
    epsilon = max(0.01, 0.08 - 0.01*(n_epi/200)) #Linear annealing from 8% to 1%
    # TODO 6 : ENV 초기화
    s = env.reset()
    ### 6 END
    done = False

    # 하나의 에피소드 수행
    while not done:
        # TODO 7 : AGENT와 ENV 상호 작용
        a = q.sample_action(torch.from_numpy(s).float(), epsilon)
        s_prime, r, done, info = env.step(a) # 스텝 반복
        
        done_mask = 0.0 if done else 1.0
        memory.put((s,a,r/100.0,s_prime, done_mask)) # reward가 너무 커지지 않도록, reward의 합이 10미만이 되도록 reward/100을 해줌
        s = s_prime
        ### 7 END
        score += r
        if done:
            break
        
    # buffer size가 2000개 넘을때부터 neural net 학습시킴 (에피소드 개수가 너무 적으면 학습X)
    if memory.size()>2000:
        train(q, q_target, memory, optimizer)

    if n_epi%print_interval==0 and n_epi!=0:
        # TODO 8 : statedict사용 하여 q_target을 업데이트
        q_target.load_state_dict(q.state_dict())
        ###
        print("n_episode :{}, score : {:.1f}, n_buffer : {}, eps : {:.1f}%".format(
                                                        n_epi, score/print_interval, memory.size(), epsilon*100))
        score = 0.0
env.close()