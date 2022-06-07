
from dataclasses import field
import json
from logging import exception
from pickle import TRUE
from textwrap import indent
from venv import create
from flask import Flask,flash, render_template
from flask import request

import shotgun_api3


app=Flask(__name__)

sg= shotgun_api3.Shotgun(
        "https://cocoavision.shotgunstudio.com",
        script_name="icentric",
        api_key="msfqmpyody^hc6ummlqfatbmN",
        )

@app.route('/excelUpload',methods=['POST'])
def uploadExcel():
        dataDictForm= dict(request.form.to_dict())
    
        return render_template("excelUploader.html",projectID=dataDictForm['project_id'])
    
@app.route('/excelUploadImplement',methods=['POST'])
def uploadExcelImplement():
    
    dataPassedFromHTML=dict(request.form.to_dict())                               #html 데이터 로드
    rowslen=int(dataPassedFromHTML['len'])                                        #데이터 길이 로드
    projectID=int(dataPassedFromHTML['ProjectID'])                                #프로젝트 아이디 로드
    sg_Shot_Fields=sg.schema_field_read('Shot')                             #Shot 필드목록 획득 
    sg_FieldsAndName={}                                               #Shot필드 목록의 웹 상 필드명과 실제 필드명 맵핑
    for key,value in sg_Shot_Fields.items():
        sg_FieldsAndName[value['name']['value']]=key
    
   
    sg_UserNameToID={}                                                        #샷그리드 유저 로드
    for user in sg.find('HumanUser',[],['name']):                   #유저 아이디와 이름 맵핑
        sg_UserNameToID[user['name']]=int(user['id'])



    TaskKey={                                                       #별도 처리가 필요한 테스크, 할당자와 기한 맵핑
        "Matte":[".Matte_assginee",".Matte_date"],
        "Motion":[".Motion_assginee",".Motion_date"],
        "Tracking":[".Tracking_assginee",".Tracking_date"],
        "FX":[".FX_assginee",".FX_date"],
        "3D":[".3D_assginee",".3D_date"],
        "RO/RI":[".RO/RI_assginee",".RO/RI_date"],
        "2D":[".2D_assginee",".2D_date"],
        "Rt/Sc/Tf":[".Rt/Sc/Tf",".NONE"]
        }
    
    sg_CreatedTasks=[]                                                  #생성된 태스크 관리 리스트
    sg_CreatedShots=[]                                                  #생성된 샷 관리 리스트
    sg_CreatedSeqs=[]                                                   #생성된 시퀸스 관리 리스트

    try:
        for i in range(0,rowslen):
            dataDictForm={}                                 
            query= 'dataArr['+str(i)+']'                            #HTML로 로드된 데이터 base query
            sg_Tasks=[]
            for key,val in TaskKey.items():                         #테스크 처리부
                sg_Assignees =[]
                due_date= None                                       
                if query+'['+val[0]+']' not in dataPassedFromHTML and query+'['+val[1]+']' not in dataPassedFromHTML:continue       #데이터에 assignee와 due_date가 존재하지 않는다면 건너뜀
                if query+'['+val[0]+']' in dataPassedFromHTML:                                                        #데이터에 assignee가 존재한다면
                    for assignee in dataPassedFromHTML[query+'['+val[0]+']'].split(","):                              #str형태로 넘어온 유저데이터를 기반으로 각 유저 별로
                        if assignee in sg_UserNameToID.keys():                                                        #샷그리드에서 조회한 유저 목록에 있는지를 판별 후
                            sg_Assignees.append(sg_UserNameToID[assignee])                                            #유저 목록에 존재한다면 Assignees배열에 유저 id를 저장 
                if query+'['+val[1]+']' in dataPassedFromHTML:                                                        #데이터에 due_date가 존재한다면
                    due_date=dataPassedFromHTML[query+'['+val[1]+']']                                                 #날짜 데이터를 획득
                
                sg_users=[]                                                                               
                for assigned in sg_Assignees:                                                              #유저 아이디를 기반으로 할당해야 하는 shotgrid user entity를 로드                     
                    sg_users.append(sg.find_one('HumanUser',[['id','is',assigned]],[]))
                
                sg_Step=sg.find_one('Step',[['code','is',key]],[])
                taskdata={
                    'project': {'type':'Project', 'id':projectID},
                    'content': key,
                    'due_date': due_date,
                    'task_assignees':sg_users,
                    'step':sg_Step
                    }
                sg_Task=sg.create("Task",taskdata)                                                         #태스크 생성
                sg_Tasks.append(sg_Task)                                                                      #추후에 샷에 append를 위해 tasks리스트에 연결(tasks는 각 데이터 별로 생성된 tasks들을 보관)
                sg_CreatedTasks.append(sg_Task)                                                                #task를 생성된 태스크 관리 리스트에 넣는다.
            
    
            for key,val in sg_FieldsAndName.items():                                                      #html에서 넘어온 샷그리드 웹 상 필드명을, 실제 필드명으로 변환 후 저장
                secQuery=query+'['+ key+']'
                if secQuery in dataPassedFromHTML:
                    dataDictForm[val]= dataPassedFromHTML[secQuery]
            
            if 'sg_sequence' in dataDictForm:                                                               #sequence필드 처리부
                seqId=dataDictForm['sg_sequence']
                filter=[
                ['project', 'is', {'type': 'Project', 'id': projectID}],
                ['code','is',seqId]
                ]
                sg_Seq=sg.find_one('Sequence',filter,['shots'])
                if sg_Seq == None:                                                                         #시퀸스가 존재하지 않을 시 생성
                    seqData={
                    'project': {'type':'Project', 'id':projectID},
                    'code': seqId
                    }
                    sg_Seq=sg.create('Sequence',seqData)
                    sg_CreatedSeqs.append(sg_Seq)                                                              #에러 발생 시 삭제를 위해, 리스트에 저장 
                dataDictForm['sg_sequence'] = sg_Seq                                                           #맵핑
            
            if 'sg_status_list' in dataDictForm:                                                            #데이터에 기재된 status를 샷그리드 엔티티에서 찾아서 맵핑
                sg_Status= sg.find_one("Status",[['name','is',dataDictForm['sg_status_list']]],['name','code'])
                dataDictForm['sg_status_list'] = sg_Status['code'] 
            
            if 'sg_cut_duration' in dataDictForm:                                                           #sg_cut_duration을 str에서 int형으로 변환(샷그리드 필드가 int형)
                dataDictForm['sg_cut_duration']= int(dataDictForm['sg_cut_duration'])
            
            hyperlink={}                                                                                #샷 생성 후 첨부 파일을 처리하기 위한 딕셔너리
            
            if 'sg_plate' in dataDictForm:                                                                  #sg_plate에 포함되어야 하는 첨부파일 맵핑
                link = dataDictForm['sg_plate']
                hyperlink['sg_plate']=link
                del dataDictForm['sg_plate']                                                                #없으면 에러 발생
                
            if 'sg_src' in dataDictForm:                                                                    #sg_src에 포함되어야 하는 첨부파일 맵핑
                link = dataDictForm['sg_src']
                hyperlink['sg_src']=link
                del dataDictForm['sg_src']
                
                        
            if 'sg_mov' in dataDictForm:                                                                    #sg_mov에 포합되어야 하는 첨부파일 맵핑
                link = dataDictForm['sg_mov']
                hyperlink['sg_mov']=link
                del dataDictForm['sg_mov']
            
            if 'sg_shot_name' in dataDictForm:                                                              #sg_shot_name은 code로 변경
                dataDictForm['code'] = dataDictForm['sg_shot_name']
                del dataDictForm['sg_shot_name']
         
            dataDictForm['project']= {'type':'Project', 'id':projectID}                                     #html데이터엔 project관련부가 없어서 별도로 맵핑
            dataDictForm['tasks'] = sg_Tasks                                                                #샷에 생성된 태스크들 맵핑
            shot=sg.create('Shot',dataDictForm)                                                             #샷 생성
            

            sg_CreatedShots.append(shot)                                                                    #샷관리 리스트에 추가
            for key,val in hyperlink.items():                                                               #첨부파일 처리
                sg.upload("Shot",shot['id'],val,key)
    except shotgun_api3.ShotgunError as e:                                                                  #에러 처리부
        for task in sg_CreatedTasks:                                                                        #에러 발생시 생성된 엔티티들을 삭제
            sg.delete('Task',task['id'])
        for shot in sg_CreatedShots:
            sg.delete('Shot',shot['id'])
        for seq in sg_CreatedSeqs:
            sg.delete("Sequence",seq['id'])
        print(e.__str__())
        return e.__str__()
        
    return json.dumps({'success':True}), 200, {'ContentType':'application/json'}

@app.route('/delSequence',methods=['POST'])
def delSequence():
    try:
        dataDictForm= dict(request.form.to_dict())
        selectedIds=dataDictForm['selected_ids'].split(',')                                                     #생성된 시퀸스들의 아이디를 리스트 형태로 가져옴
        
        req = {'sequence':[],'shots':[]}                                                                #html에 포스트 할 데이터
        for SeqID in selectedIds:
            filters =[                                                                              
                ['project', 'is', {'type': 'Project', 'id': int(dataDictForm['project_id'])}],
                ['id','is',int(SeqID)]
            ]
            fields= ['code','shots']

            sg_Seq=sg.find_one('Sequence',filters,fields)                                             #해당 프로젝트내에서 선택된 시퀸스의 code와 shots필드를 포함한 형태의 entity를 로드
            
            sg_Shots=sg_Seq['shots']                                                                     #시퀸스에 포함된 샷들로드
            for sg_Shot in sg_Shots:                      
                sg_Shot['sequence']=sg_Seq['code']                                                       #html에 종속된 sequence를 포함하기위해 필드 추가
                sg_shotExtend=sg.find_one('Shot',[['id', 'is', int(sg_Shot['id'])]],['image'])
                image=sg_shotExtend['image']                                                            #샷의 썸네일 로드
                if image == None:                                                                       #없을 시 None
                    sg_Shot['image']="None"
                else:                                                                                   #있을 시 URL맵핑
                    sg_Shot['image']=image
                sg_Shot.pop('type')                                                                        #html에서 표기 안하기 위해 type필드 제거
                req['shots'].append(sg_Shot)                                                               #샷 데이터 추가


            sg_Seq.pop('shots')
            req['sequence'].append(sg_Seq)

        return render_template("delSequence.html", data=req)
    except:
        return render_template("error.html", data=req)                                                  #에러 페이지
    
@app.route('/delImplement',methods=['POST'])
def delImplement():
    dataDictForm=dict(request.form.to_dict())
    idLen = int(dataDictForm['IdLen'])
    seqIdLen = int(dataDictForm['seqIDLen'])

    for i in range(0,idLen):
        nextKey = 'Ids['+str(i)+']'
        sg.delete('Shot',int(dataDictForm[nextKey]))

    for i in range(0,seqIdLen):
        nextKey = 'seqID['+str(i)+']'
        sg.delete('Sequence',int(dataDictForm[nextKey]))

    return json.dumps({'success':True}), 200, {'ContentType':'application/json'} 


if __name__=='__main__':
    app.run(debug=True)
