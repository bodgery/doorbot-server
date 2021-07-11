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

        try {
            app = docker.build( "doorbot" )

            app.inside {
                // Build config file
                sh 'rm -f config.yml'

                withCredentials([
                    string(
                        credentialsId: 'rfid-dev-db-password'
                        ,variable: 'RFID_DB_PASSWORD'
                    )
                ]) {
                    def example_conf = 'config.yml.example'
                    def conf = readYaml file: example_conf

                    conf.postgresql.passwd = RFID_DB_PASSWORD
                    conf.postgresql.username = 'doorbot'
                    conf.postgresql.database = 'doorbot-' + project_uuid
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
}