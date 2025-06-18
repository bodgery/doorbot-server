node {
    def app
    def branch_tag
    def project_uuid = UUID.randomUUID().toString()

    stage('Fetch') {
        checkout scm
    }

    stage('Build') {
        slackSend(
            color: 'good',
            message: "Started build of doorbot server [build #${env.BUILD_NUMBER}, branch ${env.BRANCH_NAME}] (<${env.BUILD_URL}|Open>)"
        )

        // Create cookie session key
        // Note that this means existing sessions will be invalidated 
        // with each release
        // Based on https://shunchaowang.wordpress.com/2015/03/10/generate-random-string-with-groovy/
        // But modified with a secure random generator
        def random = new java.security.SecureRandom()
        def pool = [ 'a'..'f', 0..9 ].flatten()
        def randomChars = (1..64).collect {
            pool[random.nextInt(pool.size())]
        }
        def session_key = randomChars.join("")



        try {
            app = docker.build( "doorbot" )

            app.inside {
                // Build config file
                sh 'rm -f config.yml'

                withCredentials([
                    string(
                        credentialsId: 'rfid-dev-db-password'
                        ,variable: 'RFID_DB_PASSWORD'
                    ),
                    string(
                        credentialsId: 'mms-password'
                        ,variable: 'MMS_PASSWORD'
                    )
                ]) {
                    def example_conf = 'config.yml.example'
                    def conf = readYaml file: example_conf

                    conf.postgresql.passwd = RFID_DB_PASSWORD
                    conf.postgresql.username = 'doorbot'
                    conf.postgresql.database = 'doorbot'
                    conf.postgresql.host = 'host.docker.internal'
                    conf.postgresql.port = 5432
                    conf.memberpress.user = 'tmurray@wumpus-cave.net'
                    conf.memberpress.passwd = MMS_PASSWORD
                    conf.oauth.expires_days = 180
                    conf.oauth.token_hex_length = 64
                    conf.session.key = session_key
                    conf.build_id = env.BUILD_ID
                    conf.build_branch = env.BRANCH_NAME
                    conf.build_date = env.BUILD_TIMESTAMP

                    writeYaml file: 'config.yml', data: conf
                }
            }
        }
        catch( err ) {
            slackSend(
                color: '#ff0000',
                message: "Failed build of doorbot server during Build stage [build #${env.BUILD_NUMBER}, branch ${env.BRANCH_NAME}] (<${env.BUILD_URL}|Open>)"
            )
            throw err
        }
    }

    stage( 'Test' ) {
        try {
            app.inside {
                dir( "t" ) {
                    sh 'PYTHONPATH=./:../:${PYTHONPATH} python3 -m nose2'
                }
            }
        }
        catch( err ) {
            slackSend(
                color: '#ff0000',
                message: "Failed build of doorbot server during Test stage [build #${env.BUILD_NUMBER}, branch ${env.BRANCH_NAME}] (<${env.BUILD_URL}|Open>)"
            )
            throw err
        }
    }

    stage( 'Push to Docker Reg' ) {
        try {
            docker.withRegistry(
                'https://docker.shop.thebodgery.org',
                ,'docker_reg'
            ) {
                branch_tag = "${env.BRANCH_NAME}-latest"
                branch_tag_uuid = "${env.BRANCH_NAME}-${project_uuid}"
                branch_tag_build = "${env.BRANCH_NAME}-${env.BUILD_NUMBER}"

                app.push( branch_tag )
                app.push( branch_tag_uuid )
                app.push( branch_tag_build )
            }
        }
        catch( err ) {
            slackSend(
                color: '#ff0000',
                message: "Failed build of doorbot server during Push Docker Reg  stage [build #${env.BUILD_NUMBER}, branch ${env.BRANCH_NAME}] (<${env.BUILD_URL}|Open>)"
            )
            throw err
        }
    }

    stage( 'Pull to Environment' ) {
        withCredentials([
            sshUserPrivateKey(
                keyFileVariable: 'SSH_KEY_PATH'
                ,usernameVariable: 'SSH_USERNAME'
                ,credentialsId: 'rfid_dev_ssh'
            )
            ,usernamePassword(
                usernameVariable: 'DOCKER_USER'
                ,passwordVariable: 'DOCKER_PASS'
                ,credentialsId: 'docker_reg'
            )
        ]) {
            def remote = [:]
            remote.name = "jenkins"
            remote.user = SSH_USERNAME
            remote.identityFile = SSH_KEY_PATH
            remote.host = "10.0.4.164"
            remote.allowAnyHosts = true

            // Only pull the main-latest branch to dev
            try {
                sshCommand(
                    remote: remote
                    ,command: "docker login -u ${DOCKER_USER} -p '${DOCKER_PASS}' https://docker.shop.thebodgery.org && docker pull docker.shop.thebodgery.org/doorbot:main-latest"
                )
            }
            catch( err ) {
                slackSend(
                    color: '#ff0000',
                    message: "Failed pulling to environment; ${env.BUILD_ID} on ${env.BRANCH_NAME} (${env.BUILD_URL})"
                )
                throw err
            }
        }
    }

    stage( 'Run on Environment' ) {
        withCredentials([
            sshUserPrivateKey(
                keyFileVariable: 'SSH_KEY_PATH'
                ,usernameVariable: 'SSH_USERNAME'
                ,credentialsId: 'rfid_dev_ssh'
            )
        ]) {
            def remote = [:]
            remote.name = "jenkins"
            remote.user = SSH_USERNAME
            remote.identityFile = SSH_KEY_PATH
            remote.host = "10.0.4.164"
            remote.allowAnyHosts = true

            try {
                sshCommand(
                    remote: remote
                    ,command: "/usr/local/bin/start_docker.sh doorbot:main-latest rfid-dev"
                )
            }
            catch( err ) {
                slackSend(
                    color: '#ff0000',
                    message: "Failed executing in environment; ${env.BUILD_ID} on ${env.BRANCH_NAME} (${env.BUILD_URL})"
                )
                throw err
            }
        }
    }

    stage( 'Finish' ) {
        slackSend(
            color: 'good',
            message: "Build finished; ${env.BUILD_ID} on ${env.BRANCH_NAME} (${env.BUILD_URL})"
        )
    }
}
