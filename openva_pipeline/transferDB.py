#------------------------------------------------------------------------------#
# transferDB.py
#
# Notes
#
# -- exceptions appear at end of file
# 
# (1) This class should have a methods: connect; configODK, configOpenVA,
#     configDHIS2, storeVA, storeBlob, logDB, & logFile
#
#  you could use connect as a context (and thus close it every time)
#  but this might be a waste of resources to open and close everytime?
# 
#------------------------------------------------------------------------------#

import os
import collections
import datetime
from pipeline import PipelineError
from pysqlcipher3 import dbapi2 as sqlcipher

class TransferDB:
    """This class handles interactions with the Transfer database.

    The Pipeline accesses configuration information from the Transfer database,
    and also stores log messages and verbal autopsy records in the DB.  The
    Transfer database is encrypted using sqlcipher3 (and the pysqlcipher3
    module is imported to establish DB connection).

    Parameters
    ----------
    dbFileName : str
        File name of the Tranfser database.
    dbDirectory : str
        Path of folder containing the Transfer database.
    dbKey : str
        Encryption key for the Transfer database.

    Methods
    -------
    connectDB(self)
        Returns SQLite Connection object to Transfer database.
    configPipeline(self, conn)
        Accepts SQLite Connection object and returns tuple with configuration
        settings for the Pipeline.
    configODK(self, conn)
        Accepts SQLite Connection object and returns tuple with configuration
        settings for connecting to ODK Aggregate server.
    configOpenVA(self, conn)
        Accepts SQLite Connection object and returns tuple with configuration
        settings for R package openVA.
    configDHIS(self, conn)
        Accepts SQLite Connection object and returns tuple with configuration
        settings for connecting to DHIS2 server.

    """


    def __init__(self, dbFileName, dbDirectory, dbKey):

        self.dbFileName = dbFileName
        self.dbDirectory = dbDirectory
        self.dbKey = dbKey
        self.dbPath = os.path.join(dbDirectory, dbFileName)


    def connectDB(self):
        """Connect to Transfer database.

        Uses parameters supplied to the parent class, TransferDB, to connect to
        the (encrypted) Transfer database.

        Returns
        -------
        SQLite database connection object
            Used to query (encrypted) SQLite database.
                    
        Raises
        ------
        DatabaseConnectionError

        """

        dbFilePresent = os.path.isfile(self.dbPath)
        if not dbFilePresent:
            raise DatabaseConnectionError("")

        conn = sqlcipher.connect(self.dbPath)
        parSetKey = "\"" + self.dbKey + "\""
        conn.execute("PRAGMA key = " + parSetKey)

        return(conn)

    # def logDB(self):
    #     pass

    # def logFile(self):
    #     pass

    def configPipeline(self, conn):
        """Grabs Pipline configuration settings.

        This method queries the Pipeline_Conf table in Transfer database and
        returns a tuple with attributes (1) algorithmMetadataCode; (2)
        codSource; (3) algorithm; and (4) workingDirectory.

        Returns
        -------
        tuple
            alogrithmMetadataCode - attribute describing VA data
            codSource - attribute detailing the source of the Cause of Death list
            algorithm - attribute indicating which VA algorithm to use
            workingDirectory - attribute indicating the working directory

        Raises
        ------
        PipelineConfigurationError

        """

        c = conn.cursor()

        c.execute("SELECT dhisCode from Algorithm_Metadata_Options;")
        metadataQuery = c.fetchall()
        c.execute("SELECT algorithmMetadataCode FROM Pipeline_Conf;")
        algorithmMetadataCode = c.fetchone()[0]
        if algorithmMetadataCode not in [j for i in metadataQuery for j in i]:
            raise PipelineConfigurationError \
                ("Problem in database: Pipeline_Conf.algorithmMetadataCode")

        c.execute("SELECT codSource FROM Pipeline_Conf;")
        codSource = c.fetchone()[0]
        if codSource not in ("ICD10", "WHO", "Tariff"):
            raise PipelineConfigurationError \
                ("Problem in database: Pipeline_Conf.codSource")

        c.execute("SELECT algorithm FROM Pipeline_Conf;")
        algorithm = c.fetchone()[0]
        if algorithm not in ("InterVA", "Insilico", "SmartVA", "InterVA5"):
            raise PipelineConfigurationError \
                ("Problem in database: Pipeline_Conf.algorithm")

        c.execute("SELECT workingDirectory FROM Pipeline_Conf;")
        workingDirectory = c.fetchone()[0]
        if not os.path.isdir(workingDirectory):
            raise PipelineConfigurationError \
                ("Problem in database: Pipeline_Conf.workingDirectory")

        ntPipeline = collections.namedtuple("ntPipeline",
                                            ["algorithmMetadataCode",
                                             "codSource",
                                             "algorithm",
                                             "workingDirectory"]
        )
        settingsPipeline = ntPipeline(algorithmMetadataCode,
                                      codSource,
                                      algorithm,
                                      workingDirectory)
        return(settingsPipeline)

    def configODK(self, conn):
        """Query ODK configuration settings from database.

        This method is intended to be used in conjunction with
        (1) TransferDB.connectDB(), which establishes a connection to a
        database with the Pipeline configuration settings; and (2)
        ODK.connect(), which establishes a connection to an ODK Aggregate
        server.  Thus, ODK.config() gets its input from TransferDB.connectDB()
        and the output from ODK.config() is a valid argument for ODK.config().

        Parameters
        ----------
        conn : sqlite3 Connection object

        Returns
        -------
        tuple
            Contains all parameters for ODK.connect().

        Raises
        ------
        ODKConfigurationError

        """
        c = conn.cursor()
        sqlODK = "SELECT odkID, odkURL, odkUser, odkPassword, odkFormID, \
          odkLastRun, odkLastRunResult FROM ODK_Conf;"
        queryODK = c.execute(sqlODK).fetchall()
        odkID = queryODK[0][0]

        odkURL = queryODK[0][1]
        startHTML = odkURL[0:7]
        startHTMLS = odkURL[0:8]
        if not (startHTML == "http://" or startHTMLS == "https://"):
            raise ODKConfigurationError \
                ("Problem in database: ODK_Conf.odkURL")

        odkUser = queryODK[0][2]
        odkPassword = queryODK[0][3]
        odkFormID = queryODK[0][4]
        odkLastRun = queryODK[0][5]
        odkLastRunResult = queryODK[0][6]
        odkLastRunDate = datetime.datetime.strptime(odkLastRun,
                                                    "%Y-%m-%d_%H:%M:%S"
                                                   ).strftime("%Y/%m/%d")
        odkLastRunDatePrev = (datetime.datetime.strptime(odkLastRunDate,
                                                         "%Y/%m/%d") - \
                              datetime.timedelta(days=1)).strftime("%Y/%m/%d")

        ntODK = collections.namedtuple("ntODK",
                                       ["odkID",
                                        "odkURL",
                                        "odkUser",
                                        "odkPassword",
                                        "odkFormID",
                                        "odkLastRun",
                                        "odkLastRunResult",
                                        "odkLastRunDate",
                                        "odkLastRunDatePrev"]
        )
        settingsODK = ntODK(odkID,            
                            odkURL,           
                            odkUser,          
                            odkPassword,      
                            odkFormID,        
                            odkLastRun,       
                            odkLastRunResult, 
                            odkLastRunDate,   
                            odkLastRunDatePrev)

        return(settingsODK)

    def configOpenVA(self, conn, algorithm, pipelineDir):
        """Query OpenVA configuration settings from database.

        This method is intended to receive its input (a Connection object) 
        from TransferDB.connectDB(), which establishes a connection to a
        database with the Pipeline configuration settings.  It sets up the
        configuration for all of the VA algorithms included in the R package
        openVA.  The output from configOpenVA() serves as an input to the
        method OpenVA.setAlgorithmParameters().  This is a wrapper function
        that calls __configInterVA__, __configInSilicoVA__, and
        __configSmartVA__ to actually pull configuration settings from the
        database.

        Parameters
        ----------
        conn : sqlite3 Connection object
        algorithm : VA algorithm used by R package openVA
        pipelineDir : Working directory for the Pipeline

        Returns
        -------
        tuple
            Contains all parameters needed for OpenVA.setAlgorithmParameters().

        Raises
        ------
        OpenVAConfigurationError
        """

        if(algorithm in ("InterVA4", "InterVA5")):
            settingsInterVA = self.__configInterVA__(conn, pipelineDir)
            return(settingsInterVA)
        elif(algorithm == "InSilicoVA"):
            settingsInSilicoVA = self.__configInSilicoVA__(conn, pipelineDir)
            return(settingsInSilicoVA)
        else:
            settingsSmartVA = self.__configSmartVA__(conn, pipelineDir)
            return(settingsSmartVA)

    def __configInterVA__(self, conn, pipelineDir):
        """Query OpenVA configuration settings from database.

        This method is called by configOpenVA when the VA algorithm is either
        InterVA4 or InterVA5.

        Parameters
        ----------
        conn : sqlite3 Connection object
        pipelineDir : Working directory for the Pipeline

        Returns
        -------
        tuple
            Contains all parameters needed for OpenVA.setAlgorithmParameters().

        Raises
        ------
        OpenVAConfigurationError
        """

        c = conn.cursor()

        sqlInterVA = "SELECT version, HIV, Malaria FROM InterVA_Conf;"
        queryInterVA = c.execute(sqlInterVA).fetchall()

        # Database Table: InterVA_Conf
        intervaVersion = queryInterVA[0][0]
        if not intervaVersion in ("4", "5"):
            raise OpenVAConfigurationError \
                ("Problem in database: InterVA_Conf.version \
                (valid options: '4' or '5').")
        intervaHIV = queryInterVA[0][1]
        if not intervaHIV in ("v", "l", "h"):
            raise OpenVAConfigurationError \
                ("Problem in database: InterVA_Conf.HIV \
                (valid options: 'v', 'l', or 'h').")
        intervaMalaria = queryInterVA[0][2]
        if not intervaMalaria in ("v", "l", "h"):
            raise OpenVAConfigurationError \
                ("Problem in database: InterVA_Conf.Malaria \
                (valid options: 'v', 'l', or 'h').")
        
        # Database Table: Advanced_InterVA_Conf
        sqlAdvancedInterVA = "SELECT directory, filename, output, append, \
        groupcode, replicate, replicate_bug1, replicate_bug2, write \
        FROM Advanced_InterVA_Conf;"
        queryAdvancedInterVA = c.execute(sqlAdvancedInterVA).fetchall()

        intervaDirectory = queryAdvancedInterVA[0][0]
        intervaPath = os.path.join(pipelineDir, intervaDirectory)
        if not os.path.isdir(intervaPath):
            raise OpenVAConfigurationError \
                ("Problem in database: Advanced_InterVA_Conf.directory.")
        intervaFilename = queryAdvancedInterVA[0][1]
        if intervaFilename == None or intervaFilename == "":
            raise OpenVAConfigurationError \
                ("Problem in database: Advanced_InterVA_Conf.filename.")
        intervaOutput = queryAdvancedInterVA[0][2]
        if not intervaOutput in ("classic", "extended"):
            raise OpenVAConfigurationError \
                ("Problem in database: Advanced_InterVA_Conf.output.")
        intervaAppend = queryAdvancedInterVA[0][3]
        if not intervaAppend in ("TRUE", "FALSE"):
            raise OpenVAConfigurationError \
                ("Problem in database: Advanced_InterVA_Conf.append.")
        intervaGroupcode = queryAdvancedInterVA[0][4]
        if not intervaGroupcode in ("TRUE", "FALSE"):
            raise OpenVAConfigurationError \
                ("Problem in database: Advanced_InterVA_Conf.groupcode.")
        intervaReplicate = queryAdvancedInterVA[0][5]
        if not intervaReplicate in ("TRUE", "FALSE"):
            raise OpenVAConfigurationError \
                ("Problem in database: Advanced_InterVA_Conf.replicate.")
        intervaReplicateBug1 = queryAdvancedInterVA[0][6]
        if not intervaReplicateBug1 in ("TRUE", "FALSE"):
            raise OpenVAConfigurationError \
                ("Problem in database: Advanced_InterVA_Conf.replicate_bug1.")
        intervaReplicateBug2 = queryAdvancedInterVA[0][7]
        if not intervaReplicateBug2 in ("TRUE", "FALSE"):
            raise OpenVAConfigurationError \
                ("Problem in database: Advanced_InterVA_Conf.replicate_bug2.")
        intervaWrite = queryAdvancedInterVA[0][8]
        if not intervaWrite in ("TRUE", "FALSE"):
            raise OpenVAConfigurationError \
                ("Problem in database: Advanced_InterVA_Conf.write.")
        
        ntInterVA = collections.namedtuple("ntInterVA",
                                           ["InterVA_Version",
                                            "InterVA_HIV",
                                            "InterVA_Malaria",
                                            "InterVA_directory",
                                            "InterVA_filename",
                                            "InterVA_output",
                                            "InterVA_append",
                                            "InterVA_groupcode",
                                            "InterVA_replicate",
                                            "InterVA_replicate_bug1",
                                            "InterVA_replicate_bug2",
                                            "InterVA_write"]
        )
        settingsInterVA = ntInterVA(intervaVersion,
                                    intervaHIV,
                                    intervaMalaria,
                                    intervaDirectory,
                                    intervaFilename,
                                    intervaOutput,
                                    intervaAppend,
                                    intervaGroupcode,
                                    intervaReplicate,
                                    intervaReplicateBug1,
                                    intervaReplicateBug2,
                                    intervaWrite)
        return(settingsInterVA)

    def __configInSilicoVA__(self, conn, pipelineDir):
        """Query OpenVA configuration settings from database.

        This method is called by configOpenVA when the VA algorithm is
        InSilicoVA.

        Parameters
        ----------
        conn : sqlite3 Connection object
        pipelineDir : Working directory for the Pipeline

        Returns
        -------
        tuple
            Contains all parameters needed for OpenVA.setAlgorithmParameters().

        Raises
        ------
        OpenVAConfigurationError
        """

        c = conn.cursor()

        # Database Table: InSilicoVA_Conf
        sqlInSilicoVA = "SELECT data_type, Nsim FROM InSilicoVA_Conf;"
        queryInSilicoVA = c.execute(sqlInSilicoVA).fetchall()

        insilicovaDataType = queryInSilicoVA[0][0]
        if not insilicovaDataType in ("WHO2012", "WHO2016"):
            raise OpenVAConfigurationError \
                ("Problem in database: InSilicoVA_Conf.data_type \
                (valid options: 'WHO2012' or 'WHO2016').")
        insilicovaNsim = queryInSilicoVA[0][1]
        if insilicovaNsim in ("", None):
            raise OpenVAConfigurationError \
                ("Problem in database: InSilicoVA_Conf.Nsim")

        # Database Table: Advanced_InSilicoVA_Conf
        sqlAdvancedInSilicoVA = "SELECT isNumeric, updateCondProb, \
          keepProbbase_level, CondProb, CondProbNum, datacheck, \
          datacheck_missing, warning_write, directory, external_sep, thin, \
          burnin, auto_length, conv_csmf, jump_scale, levels_prior, \
          levels_strength, trunc_min, trunc_max, subpop, java_option, seed, \
          phy_code, phy_cat, phy_unknown, phy_external, phy_debias, \
          exclude_impossible_cause, no_is_missing, indiv_CI, groupcode \
          FROM Advanced_InSilicoVA_Conf;"
        queryAdvancedInSilicoVA = c.execute(sqlAdvancedInSilicoVA).fetchall()
        insilicovaIsNumeric = queryAdvancedInSilicoVA[0][0]
        if not insilicovaIsNumeric in ("TRUE", "FALSE"):
            raise OpenVAConfigurationError \
                ("Problem in database: InSilicoVA_Conf.isNumeric \
                (valid options: 'TRUE' or 'FALSE').")

        ntInSilicoVA = collections.namedtuple("ntInSilicoVA",
                                              ["InSilicoVA_data_type",
                                               "InSilicoVA_Nsim",
                                               "InSilicoVA_isNumeric"])
                                               # "InSilicoVA_updateCondProb",
                                               # "InSilicoVA_keepProbbase_level",
                                               # "InSilicoVA_CondProb",
                                               # "InSilicoVA_CondProbNum",
                                               # "InSilicoVA_datacheck",
                                               # "InSilicoVA_datacheck_missing",
                                               # "InSilicoVA_warning_write",
                                               # "InSilicoVA_directory",
                                               # "InSilicoVA_external_sep",
                                               # "InSilicoVA_thin",
                                               # "InSilicoVA_burnin",
                                               # "InSilicoVA_auto_length",
                                               # "InSilicoVA_conv_csmf",
                                               # "InSilicoVA_jump_scale",
                                               # "InSilicoVA_levels_prior",
                                               # "InSilicoVA_levels_strength",
                                               # "InSilicoVA_trunc_min",
                                               # "InSilicoVA_trunc_max",
                                               # "InSilicoVA_subpop",
                                               # "InSilicoVA_java_option",
                                               # "InSilicoVA_seed",
                                               # "InSilicoVA_phy_code",
                                               # "InSilicoVA_phy_cat",
                                               # "InSilicoVA_phy_unknown",
                                               # "InSilicoVA_phy_external",
                                               # "InSilicoVA_phy_debias",
                                               # "InSilicoVA_exclude_impossible_cause",
                                               # "InSilicoVA_no_is_missing",
                                               # "InSilicoVA_indiv_CI",
                                               # "InSilicoVA_groupcode"]
        #)
        settingsInSilicoVA = ntInSilicoVA(insilicovaDataType,
                                          insilicovaNsim,
                                          insilicovaIsNumeric)
                                          # insilicovaUpdateCondProb,
                                          # insilicovaKeepProbbaseLevel,
                                          # insilicovaCondProb,
                                          # insilicovaCondProbNum,
                                          # insilicovaDatacheck,
                                          # insilicovaDatacheckMissing,
                                          # insilicovaWarningWrite,
                                          # insilicovaDirectory,
                                          # insilicovaExternalSep,
                                          # insilicovaThin,
                                          # insilicovaBurnin,
                                          # insilicovaAutoLength,
                                          # insilicovaConvCsmf,
                                          # insilicovaJumpScale,
                                          # insilicovaLevelsPrior,
                                          # insilicovaLevelsStrength,
                                          # insilicovaTruncMin,
                                          # insilicovaTruncMax,
                                          # insilicovaSubpop,
                                          # insilicovaJavaOption,
                                          # insilicovaSeed,
                                          # insilicovaPhyCode,
                                          # insilicovaPhyCat,
                                          # insilicovaPhyUnknown,
                                          # insilicovaPhyExternal,
                                          # insilicovaPhyDebias,
                                          # insilicovaExcludeImpossibleCause,
                                          # insilicovaNoIsMissing,
                                          # insilicovaIndivCI,
                                          # insilicovaGroupcode)
        return(settingsInSilicoVA)

    def __configSmartVA__(self, conn, pipelineDir):
        """Query OpenVA configuration settings from database.

        This method is called by configOpenVA when the VA algorithm is
        SmartVA.

        Parameters
        ----------
        conn : sqlite3 Connection object
        pipelineDir : Working directory for the Pipeline

        Returns
        -------
        tuple
            Contains all parameters needed for OpenVA.setAlgorithmParameters().

        Raises
        ------
        OpenVAConfigurationError
        """

        pass

    def configDHIS(self):
        """Query DHIS configuration settings from database.

        This method is intended to be used in conjunction with
        (1) TransferDB.connectDB(), which establishes a connection to a
        database with the Pipeline configuration settings; and (2)
        ODK.connect(), which establishes a connection to an ODK Aggregate
        server.  Thus, ODK.config() gets its input from TransferDB.connectDB()
        and the output from ODK.config() is a valid argument for ODK.config().

        Parameters
        ----------
        conn : sqlite3 Connection object

        Returns
        -------
        tuple
            Contains all parameters for ODK.connect().

        Raises
        ------
        DHISConfigurationError

        """
        pass

    def storeVA(self):
        """Query ODK configuration settings from database.

        This method is intended to be used in conjunction with
        (1) TransferDB.connectDB(), which establishes a connection to a
        database with the Pipeline configuration settings; and (2)
        ODK.connect(), which establishes a connection to an ODK Aggregate
        server.  Thus, ODK.config() gets its input from TransferDB.connectDB()
        and the output from ODK.config() is a valid argument for ODK.config().

        Parameters
        ----------
        conn : sqlite3 Connection object

        Returns
        -------
        tuple
            Contains all parameters for ODK.connect().

        Raises
        ------
        DatabaseConnectionError

        """
        pass

    def storeBlob(self):
        """Query ODK configuration settings from database.

        This method is intended to be used in conjunction with
        (1) TransferDB.connectDB(), which establishes a connection to a
        database with the Pipeline configuration settings; and (2)
        ODK.connect(), which establishes a connection to an ODK Aggregate
        server.  Thus, ODK.config() gets its input from TransferDB.connectDB()
        and the output from ODK.config() is a valid argument for ODK.config().

        Parameters
        ----------
        conn : sqlite3 Connection object

        Returns
        -------
        tuple
            Contains all parameters for ODK.connect().

        Raises
        ------
        DatabaseConnectionError

        """
        pass

#------------------------------------------------------------------------------#
# Exceptions
#------------------------------------------------------------------------------#
class DatabaseConnectionError(PipelineError): pass
class PipelineConfigurationError(PipelineError): pass
class ODKConfigurationError(PipelineError): pass
class OpenVAConfigurationError(PipelineError): pass
class DHISConfigurationError(PipelineError): pass
