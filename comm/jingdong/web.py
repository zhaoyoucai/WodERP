#coding:utf-8


from base import BaseHandler

from comm.jingdong.jdAPI import *
from comm.database.databaseCase import *
import json
import re
import tornado.web


class JDOrderListHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):

        user = self.current_user
        role = self.get_secure_cookie("role") if self.get_secure_cookie("role") else 'None'

        mongo = MongoCase()
        mongo.connect()
        client = mongo.client

        db = client.woderp

        pageSize = 50

        status = self.get_argument('status','')
        wd = self.get_argument('wd','')


        try:
            page = int(self.get_argument('page',1))
        except:
            page = 1

        #totalCount = db.orderList.find({"order_state":"WAIT_SELLER_STOCK_OUT"}).count()
        option = {'platform':'jingdong'}
        if status == '0':
            option['order_state'] = 'WAIT_SELLER_STOCK_OUT'
        elif status == '1':
            option['order_state'] = 'WAIT_GOODS_RECEIVE_CONFIRM'


        if wd != '':
            words = re.compile(wd)

            filerList = []
            filerList.append({'item_info_list.sku_name':words})
            filerList.append({'item_info_list.sku_id':words})
            filerList.append({'order_id':words})
            filerList.append({'consignee_info.fullname':words})
            filerList.append({'consignee_info.mobile':words})
            filerList.append({'consignee_info.telephone':words})
            filerList.append({'logisticsInfo.waybill':words})

            option['$or'] = filerList



        totalCount = db.orderList.find(option).count()

        orderList = db.orderList.find(option).sort("order_start_time",-1).limit(pageSize).skip((page-1)*pageSize)

        p = divmod(totalCount,pageSize)

        pageInfo = dict()

        totalPage = p[0]
        if p[1]>0:
            totalPage += 1

        pageInfo['totalPage'] = totalPage
        pageInfo['totalCount'] = totalCount
        pageInfo['pageSize'] = pageSize
        pageInfo['pageNo'] = page
        pageInfo['pageList'] = range(1,totalPage+1)

        filterData = dict()
        filterData['status'] = status
        filterData['wd'] = wd

        self.render('jd/order-list.html',orderList = orderList,pageInfo = pageInfo,filterData=filterData,userInfo={'account':user,'role':role})

        #self.render('index.html')

    def write_error(self, status_code, **kwargs):
        self.write("Gosh darnit, user! You caused a %d error.\n" % status_code)

class JDCheckOrderHandler(BaseHandler):
    def get(self):

        #result = o.getOrderList(order_state='WAIT_GOODS_RECEIVE_CONFIRM')

        appKey = self.get_argument('appKey','40BF94D17B3F69D29294F645AD10BFC2')

        mongo = MongoCase()
        mongo.connect()
        client = mongo.client
        db = client.jingdong

        app = db.apiInfo.find_one({'app_key':appKey})

        if app != None:

            dberp = client.woderp

            api = JDAPI(app)
            result = api.getOrderList(order_state='WAIT_SELLER_STOCK_OUT')

            ol = result['order_search_response']['order_search']['order_info_list']
            total = 0
            addCount = 0
            updateCount = 0
            for od in ol:
                item = od
                item['createTime'] = datetime.datetime.now()
                item['updateTime'] = None
                item['dealCompleteTime'] = None
                item['purchaseInfo'] = None
                item['dealRemark'] = None
                item['logisticsInfo'] = None
                item['shopId'] = '163184'
                item['platform'] = 'jingdong'
                if not item.has_key('payment_confirm_time'):
                    item['payment_confirm_time'] = None
                if not item.has_key('parent_order_id'):
                    item['parent_order_id'] = None
                if not item.has_key('pin'):
                    item['pin'] = None
                if not item.has_key('return_order'):
                    item['return_order'] = None
                if not item.has_key('order_state_remark'):
                    item['order_state_remark'] = None
                if not item.has_key('vender_remark'):
                    item['vender_remark'] = None

                item['dealStatus'] = 0
                item['stage'] = 0
                item['oprationLog'] = []

                for sku in item['item_info_list']:
                    sku['skuImg'] = None
                    sku['link'] = None
                    if not sku.has_key('product_no'):
                        sku['product_no'] = None
                    if not sku.has_key('outer_sku_id'):
                        sku['outer_sku_id'] = None
                    if not sku.has_key('ware_id'):
                        sku['ware_id'] = None


                if dberp.orderList.find({'order_id':item['order_id']}).count()>0:
                    updateCount += 1
                else:
                    dberp.orderList.insert(item)
                    addCount += 1

                total +=1

            respon = {'success': True,"data":{"total":total,"addCount":addCount,'updateCount':updateCount}}

            self.write(json.dumps(respon,ensure_ascii=False))
        else:
            self.write(json.dumps({'success':False},ensure_ascii=False))


class JDCheckSkuHandler(BaseHandler):

    def get(self):

        appKey = self.get_argument('appKey','40BF94D17B3F69D29294F645AD10BFC2')
        sku = self.get_argument('sku','')

        mongo = MongoCase()
        mongo.connect()
        client = mongo.client
        db = client.jingdong

        app = db.apiInfo.find_one({'app_key':appKey})


        data = dict()
        if sku != '' and app != None:


            api = JDAPI(app)
            result = api.searchSkuList(option={'page_size':'100','skuId':sku,'field':'wareId,skuId,status,jdPrice,outerId,categoryId,logo,skuName,stockNum,wareTitle,created'})
            sl = result['jingdong_sku_read_searchSkuList_responce']['page']['data']
            for s in sl:
                item = s
                item['createTime'] = datetime.datetime.now()
                item['updateTime'] = None
                item['shopId'] = '163184'
                item['platform'] = 'jingdong'
                item['stage'] = 0
                item['oprationLog'] = []
                item['skuId'] = str(s['skuId'])
                item['wareId'] = str(s['wareId'])

                try:
                    db.skuList.insert(item)
                except Exception as e:
                    print(e)

            data['success'] = True

        else:
            data['success'] = False

        self.write(json.dumps(data,ensure_ascii=False))



class GetJdSkuImageHandler(BaseHandler):
    def get(self):

        skuId = self.get_argument('skuId','')

        mark = 0
        imgUrl = ''
        if skuId != '':
            mongo = MongoCase()
            mongo.connect()
            client = mongo.client
            db = client.jingdong

            dberp = client.woderp

            item = db.skuList.find({"skuId":skuId},{"logo":1})
            if item.count()>0:
                imgUrl += item[0]['logo']
                dberp.orderList.update({'platform':'jingdong',"item_info_list.sku_id":skuId,"item_info_list.skuImg":None},{"$set":{"item_info_list.$.skuImg":item[0]['logo']}})


        if imgUrl == '':
            imgUrl += 'jfs/t3271/88/7808807198/85040/49d5cf69/58bccd95Nd1b090a7.jpg'
            mark += 1

        respon = {'imgUrl': imgUrl,'mark':mark}
        self.write(json.dumps(respon,ensure_ascii=False))



class JdMatchPurchaseOrderHandler(BaseHandler):

    def get(self):
        data = dict()
        ids = self.get_argument('ids', '')
        ids = ids.split(',')
        data['total'] = len(ids)
        data['matchCount'] = 0
        mongo = MongoCase()
        mongo.connect()
        client = mongo.client
        db = client.woderp
        for orderId in ids:

            order = db.orderList.find_one({'order_id':orderId})

            if order and order['order_state'] == 'WAIT_SELLER_STOCK_OUT':

                purchase = db.purchaseList.find({'toFullName':order['consignee_info']['fullname'],'toMobile':order['consignee_info']['mobile'],'createTime':{'$gte':order['createTime']}})


                if order.has_key('matchStatus') and order['matchStatus']>1 :
                    pass
                else:

                    matchItem = []
                    for item in purchase:
                        matchData = dict()
                        matchData['orderId'] = item['id']
                        matchData['orderStatus'] = item['status']
                        if item.has_key('logistics'):
                            matchData['logistics'] = item['logistics']

                        matchItem.append(matchData)


                    if len(matchItem)>0:
                        data['matchCount'] += 1
                        db.orderList.update({'order_id':orderId},{'$set':{'matchItem':matchItem,'matchStatus':1}})


        self.write(json.dumps(data,ensure_ascii=False))


class JDChcekOrderInfoHanlder(BaseHandler):

    def get(self):
        data = dict()
        orderId = self.get_argument('orderId', '')
        appKey = self.get_argument('appKey','40BF94D17B3F69D29294F645AD10BFC2')

        mongo = MongoCase()
        mongo.connect()
        client = mongo.client
        db = client.jingdong

        app = db.apiInfo.find_one({'app_key':appKey})

        if orderId != '' and app:
            dberp = client.woderp

            api = JDAPI(app)

            result = api.getOrderDetail(order_id=orderId,
                                      option={"optional_fields": "order_state,pin,waybill,logistics_id,modified,return_order,order_state_remark,vender_remark,payment_confirm_time"})
            orderInfo = result['order_get_response']['order']['orderInfo']

            item = dict()

            if orderInfo["pin"] != '':
                item['pin'] = orderInfo["pin"]

            logistics = dict()
            if orderInfo["logistics_id"] != '':
                logistics['logistics_id'] = orderInfo["logistics_id"]
                logistics['waybill'] = orderInfo["waybill"]
            if logistics != {}:
                item['logisticsInfo'] = logistics
                item['dealStatus'] = 3
            item['modified'] = orderInfo['modified']
            item['order_state'] = orderInfo['order_state']
            item['return_order'] = orderInfo['return_order']
            item['order_state_remark'] = orderInfo['order_state_remark']
            item['vender_remark'] = orderInfo['vender_remark']
            item['payment_confirm_time'] = orderInfo['payment_confirm_time']
            item['updateTime'] = datetime.datetime.now()

            dberp.orderList.update({"order_id": orderId}, {'$set': item})

            data['success'] = True
        else:
            data['success'] = False

        self.write(json.dumps(data,ensure_ascii=False))


class JDGetOrderItemsHandler(BaseHandler):

    def get(self):
        data = dict()
        orderId = self.get_argument('orderId','')

        data['items'] = []
        data['purchaseInfo'] = []
        if orderId != '':
            mongo = MongoCase()
            mongo.connect()
            client = mongo.client
            db = client.jingdong
            dberp = client.woderp


            item = dberp.orderList.find_one({"order_id":orderId},{"item_info_list":1,"purchaseInfo":1})

            if item != None:


                if item['purchaseInfo']!=None:
                    for purchase in item['purchaseInfo']:
                        purchase['createDate'] = str(purchase['createDate'])
                        data['purchaseInfo'].append(purchase)

                for sku in item['item_info_list']:
                    foo = db.skuList.find_one({"skuId":sku['sku_id']},{"logo":1})



                    for p in data['purchaseInfo']:
                        for s in p['purchaseItems']:
                            if s['sku_id'] == sku['sku_id']:
                                sku['link'] = s['link']


                    if sku['skuImg']==None and foo != None:
                        sku['skuImg'] = foo['logo']
                        dberp.orderList.update({"item_info_list.sku_id":sku['sku_id']},{"$set":{"item_info_list.$.skuImg":sku['skuImg']}})

                    data['items'].append(sku)


        self.write(json.dumps(data,ensure_ascii=False))