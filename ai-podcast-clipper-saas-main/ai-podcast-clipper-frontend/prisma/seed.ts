
import { PrismaClient } from '@prisma/client'
import { v4 as uuidv4 } from 'uuid';

const prisma = new PrismaClient()

async function main() {
  const userId = 'local-user'
  
  const existingUser = await prisma.user.findUnique({
    where: { id: userId },
  })

  if (!existingUser) {
    await prisma.user.create({
      data: {
        id: userId,
        email: 'local@dev.com',
        password: 'password', // dummy
        credits: 9999,
        name: 'Local Developer'
      },
    })
    console.log('Created local user')
  } else {
    console.log('Local user already exists')
  }
}

main()
  .then(async () => {
    await prisma.$disconnect()
  })
  .catch(async (e) => {
    console.error(e)
    await prisma.$disconnect()
    process.exit(1)
  })
