from OdinElements import OdinRead
from ManualRules import CandidateEvents
from CausalityDetection import RSTModel
from Utils import Quantifiers, getIndexFromSpan
from OntologyMapping import Ontology
from IndicatorSearch import IndicatorSearch
import os
import string
from openpyxl import Workbook
import pdb
import corenlp
import pandas as pd

class SOFIA:
    """SOFIA class. Can be invoked with:
       
       ```
       sofia = sofia = SOFIA(CoreNLP='path_to_CoreNLP')
       sentence="The intense rain caused flooding in the area. This has harmed the local populace."
       results = sofia.getOutputOnline(sentence) 
       sofia.results2excel('output.xlsx',results)
       ```
       
       In this example, results is an array of JSON objects (one per sentence submitted to SOFIA).
       The final line writes this output to an Excel file at the user specified path.
    """

    def __init__(self, CoreNLP):
        self.causalHeaders = ["Source_File", 'Query', "Score", "Relation Index", "Relation", "Relation_Type", "Indicator", "Cause Index", "Cause", "Effect Index", "Effect", "Sentence"]
        self.eventHeaders = ["Source_File", 'Query', "Score", "Event Index", "Relation", "Event_Type", "FrameNet_Frame", "Indicator", "Location", "Time", 'Agent Index', "Agent", 'Patient Index', "Patient", "Sentence"]
        self.entityHeaders = ["Source_File", 'Query', "Score", "Entity Index", "Entity", "Entity_Type", "FrameNet_Frame", "Indicator", "Qualifier", "Sentence"]
        self.variableHeaders = ["Source_File", 'Sentence', 'Indicator', 'Scoring', 'Index']        
        self.entityIndex = 0
        self.eventIndex = 0
        self.variableIndex = 0
        self.causalIndex = 0
        os.environ['CORENLP_HOME'] = CoreNLP
        self.CoreNLPclient = corenlp.CoreNLPClient(annotators=['tokenize', 
                                                               'ssplit', 
                                                               'pos', 
                                                               'parse', 
                                                               'lemma', 
                                                               'ner', 
                                                               'depparse'])


    def writeOutput(self, annotations, scoring = False):
        output = []
        file = 'userinput'
        eventReader = CandidateEvents(annotations)
        numSentences = eventReader.dataSize()
        data = eventReader.getEvents_Entities()
        self.eventReader = eventReader
        for index in range(numSentences):
            sentence_output = self.writeSentence(file, index, eventReader, data, 'None', 'None', scoring = scoring)
            output.append(sentence_output)
        return output

    def writeQueryBasedOutput(self, text, queryList):
        output = []
        file = 'userinput'
        annotations = self.annotate(text)
        eventReader = CandidateEvents(annotations)
        for query in queryList:
            query_finder= IndicatorSearch(annotations, query)
            data = eventReader.getEvents_Entities()
            query_sentences= query_finder.findQuery()
            for index in query_sentences:
                sentence_output = self.writeSentence(file, index, eventReader, data, query, query_finder, False)
                output.append(sentence_output)
        return output

    def writeSentence(self, file, index, eventReader, data, query, query_finder, scoring = False):
        output = {}
        allEvents, allEntities = data
        sentence = eventReader.getSentence(index)
        ontologyMapper = Ontology()
        self.variableIndex += 1
        varIndex = 'V{}'.format(self.variableIndex)
        scores=''
        if scoring:
            scores = ontologyMapper.stringMatching(sentence, 'WorldBank')
        output['Variables'] = dict(zip(self.variableHeaders, [str(file), sentence, query, str(scores), varIndex]))
        lemmas = eventReader.getSentenceLemmas(index)
        pos = eventReader.getSentencePOSTags(index)
        entLocalIndex = {}
        entities = allEntities[index]
        events = allEvents[index]

        entityScores={}
        output['Entities'] = []
        for span in list(entities.keys()):
            self.entityIndex += 1
            entIndex = 'N{}'.format(self.entityIndex)
            entity = entities[span]
            entLocalIndex[span] = entIndex
            #scores = ontologyMapper.stringMatching(entity["trigger"], 'WorldBank')
            score=0.0
            if query_finder!= 'None':
                score= query_finder.rankNode(entity, 'entity', sentence)
            entityScores[entIndex] = score
            entInfo = [str(file), query, str(score), entIndex, entity["trigger"].lower(), entity["frame"],
                       str(entity["FrameNetFr"]), str(scores), entity['qualifier'].lower(), sentence]
            output['Entities'].append(dict(zip(self.entityHeaders,entInfo)))
        eventLocalIndex = {}
        eventScores={}
        event2Spans=[]
        output['Events'] = []

        for span in list(events.keys()):
            event = events[span]
            self.eventIndex += 1
            evIndex = 'E{}'.format(self.eventIndex)
            eventLocalIndex[span] = evIndex
            if 'event2' in event['frame']:
                event2Spans.append(span)
                self.eventIndex -= 1
                continue
            patient = getIndexFromSpan(entLocalIndex, event['patient'][0])
            agent = getIndexFromSpan(entLocalIndex, event['agent'][0])
            score = 0.0
            if query_finder != 'None':
                score = query_finder.rankNode(event, 'event', sentence)
            eventScores[evIndex] = score

            eventInfo = [str(file), query, str(score), evIndex, event["trigger"], event["frame"], str(event["FrameNetFr"]), str(scores), event['location'],
                             event['temporal'], agent, event['agent'][1], patient, event['patient'][1], sentence]
            output['Events'].append(dict(zip(self.eventHeaders,eventInfo)))
            ##Model RST currently based only on Events. Being able to bring Entities in front???
            ###Or maybe include this portion as the merged Deep Learning Architecture?
            ###Merged with Coreference & Temporal Seq???
        for span in event2Spans:
            event = events[span]
            self.eventIndex += 1
            evIndex = 'E{}'.format(self.eventIndex)
            eventLocalIndex[span] = evIndex
            try:
                patient = getIndexFromSpan(eventLocalIndex, event['patient'][0])
            except:
                try:
                    patient= getIndexFromSpan(entLocalIndex, event['patient'][0])
                except:
                    patient=''
            try:
                agent = getIndexFromSpan(eventLocalIndex, event['agent'][0])
            except:
                try:
                    agent= getIndexFromSpan(entLocalIndex, event['agent'][0])
                except:
                    agent=''
            score = 0.0
            if query_finder != 'None':
                score = query_finder.rankNode(event, 'event', sentence)
            eventScores[evIndex] = score
            eventInfo = [str(file), query, str(score), evIndex, event["trigger"], event["frame"], str(event["FrameNetFr"]), str(scores), event['location'],
                             event['temporal'], agent, event['agent'][1], patient, event['patient'][1], sentence]
            output['Events'].append(dict(zip(self.eventHeaders,eventInfo)))
        #TODO: Fix the Causality Model
        #It currently chooses ALL the events. This is wrong, it should choose the ones that do not contain others as arguments
        rst = RSTModel(events, eventLocalIndex, entities, entLocalIndex, sentence, lemmas, pos, eventScores, entityScores)
        causalRel = rst.getCausalNodes()  ### OR TRUE
        output['Causal'] = []
        for relation in causalRel:
            self.causalIndex += 1
            cauIndex = 'R{}'.format(self.causalIndex)
            cause = relation["cause"]
            effect = relation["effect"]
            relType = relation['type']
            score = 0.0
            if query_finder != 'None':
                score = query_finder.rankNode((eventScores, cause[0], effect[0]), 'relation', sentence)
            causalInfo = [str(file), query, str(score), cauIndex, relation["trigger"], relType, str(scores),
                          cause[0], cause[1], effect[0], effect[1], sentence]
            output['Causal'].append(dict(zip(self.causalHeaders,causalInfo)))
        return output

    def getOutputOnline(self, text, scoring = False):
        annotations = self.annotate(text)
        output = self.writeOutput(annotations, scoring = scoring)
        return output
    
    def annotate(self, text):
        annotations = self.CoreNLPclient.annotate(text, output_format='json')
        self.entityIndex = 0
        self.eventIndex = 0
        self.variableIndex = 0
        self.causalIndex = 0
        return annotations

    def odinData(self, file):
        currPath= os.getcwd()
        dir= os.path.dirname(currPath)+'/'+ project+'/data/'
        filePath= dir+file
        reader= OdinRead(filePath)
        #output= reader.annotateDocument()
        output= reader.getAnnotations()
        print("Analyzing", str(file))
        return output

    def runSOFIA(self, query):
        #files= ['proposal_doc']
        files= os.listdir(project+ '/data/'+dataDir)
        ##files= ['FFP Fact Sheet_South Sudan_2018.01.17 BG', 'i8533en', 'FEWS NET South Sudan Famine Risk Alert_20170117 BG', 'FAOGIEWSSouthSudanCountryBriefSept2017 BG', '130035 excerpt BG', 'CLiMIS_FAO_UNICEF_WFP_SouthSudanIPC_29June_FINAL BG', 'FEWSNET South Sudan Outlook January 2018 BG', 'EA_Seasonal Monitor_2017_08_11 BG']
        if '.DS_Store' in files:
            files= files[:files.index('.DS_Store')]+ files[files.index('.DS_Store')+1:]
        #writeOutput(files)
        #files+= ['IPC_Annex_Indicators', 'Food_security' ]
        #files=['MONTHLY_PRICE_WATCH_AND_ANNEX_AUGUST2014_1', 'Global Weather Hazard-150305']
        writeQueryBasedOutput(files, query)
        
    def flatten(self, l):
        return [item for sublist in l for item in sublist]
    
    def results2excel(self, output_path, results):
        variables = [i['Variables'] for i in results]
        entities = self.flatten([i['Entities'] for i in results])
        events = self.flatten([i['Events'] for i in results])
        causal = self.flatten([i['Causal'] for i in results])

        variables_df = pd.DataFrame(variables)[self.variableHeaders]
        entities_df = pd.DataFrame(entities)[self.entityHeaders]
        events_df = pd.DataFrame(events)[self.eventHeaders]
        causal_df = pd.DataFrame(causal)[self.causalHeaders]

        # Create a Pandas Excel writer using XlsxWriter as the engine.
        writer = pd.ExcelWriter(output_path)

        # Write each dataframe to a different worksheet.
        variables_df.to_excel(writer, sheet_name='Variables', index=False)
        entities_df.to_excel(writer, sheet_name='Entities', index=False)
        events_df.to_excel(writer, sheet_name='Events', index=False)
        causal_df.to_excel(writer, sheet_name='Causal', index=False)

        # Close the Pandas Excel writer and output the Excel file.
        writer.save()