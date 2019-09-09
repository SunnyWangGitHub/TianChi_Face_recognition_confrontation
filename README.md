# TianChi_Face_recognition_confrontation
The solution of Face recognition confrontation competition on TianChi :  24th place (巨型菜鸟实锤)


competition link:https://tianchi.aliyun.com/competition/entrance/231745/rankingList

### method：
Ensemble Attack_Gaussian Smooth + Use Average feature face as target

### implementation environment：
+ pytorch
+ python3

### summarize：
+ 六个model ensemble 得分13.9，单model 最高特分14.4 ==>尚不清楚是我找的pytorch的人脸识别的model大部分都是辣鸡还是我ensemble的方式过于粗暴（直接使用平均梯度）所以无效？

+ 比赛本身是untarget的，我以target的方式做，以712张需要提交的图片的平均特征脸做target，是个很有效的trick
